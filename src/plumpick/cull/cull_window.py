"""The single-image culling window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QMouseEvent, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plumpick import theme
from plumpick.cull.commit import run_commit
from plumpick.cull.commit_dialog import CommitDialog
from plumpick.cull.image_view import ImageView
from plumpick.cull.library import Library, Mark
from plumpick.cull.loader import load_image

BORDER_WIDTH = 6
BORDER_COLORS = {Mark.APPROVE: "#3fb950", Mark.DELETE: "#f85149", None: "transparent"}


# (keys, action): each key is drawn as a small keycap box.
SHORTCUT_HINTS = [
    (("←", "→"), "prev/next"),
    (("K", "↑"), "keep"),
    (("X", "↓", "Del"), "reject"),
    (("R", "/"), "reset mark"),
    (("Ctrl+Enter",), "commit"),
]


class _ClickLabel(QLabel):
    """A label that acts like a button, so hints can trigger their action."""

    clicked = Signal()

    def _set_pressed(self, pressed: bool) -> None:
        if self.property("pressed") == pressed:
            return
        self.setProperty("pressed", pressed)  # styled via [pressed="true"]
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_pressed(True)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Qt keeps sending moves while the button is held; dragging off cancels the click.
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._set_pressed(self.rect().contains(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_pressed = self.property("pressed")
        self._set_pressed(False)
        if (
            was_pressed
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _clickable(label: _ClickLabel, slot: Callable[[], None]) -> _ClickLabel:
    label.setCursor(Qt.CursorShape.PointingHandCursor)
    label.clicked.connect(lambda: slot())
    return label


def _build_hints(actions: dict[str, Callable[[], None]]) -> QWidget:
    """Keycap hints; clicking a key (or its action text) runs that action.

    `actions` maps each key to its callable; the action text runs its first key's."""
    box = QWidget(objectName="hints")
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 12, 0)
    layout.setSpacing(4)
    for keys, action in SHORTCUT_HINTS:
        for key in keys:
            layout.addWidget(_clickable(_ClickLabel(key, objectName="key"), actions[key]))
        layout.addWidget(_clickable(_ClickLabel(action), actions[keys[-1]]))
        layout.addSpacing(8)
    return box


class CullWindow(QMainWindow):
    def __init__(self, library: Library) -> None:
        super().__init__()
        self.library = library

        # The frame carries the approve/delete border; the view fills what's inside it.
        self.image_frame = QFrame(objectName="imageFrame")
        self.image_view = ImageView()
        layout = QVBoxLayout(self.image_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_view)
        self.image_view.zoomChanged.connect(self._update_status)
        self.setCentralWidget(self.image_frame)

        self.commit_button = QPushButton("Commit…", clicked=self.commit)
        self.commit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep Space for navigation
        keep = lambda: self.mark_and_advance(Mark.APPROVE)
        reject = lambda: self.mark_and_advance(Mark.DELETE)
        self.hints = _build_hints(
            {
                "←": self.prev_image,
                "→": self.next_image,
                "K": keep,
                "↑": keep,
                "X": reject,
                "↓": reject,
                "Del": reject,
                "R": self.clear_mark,
                "/": self.clear_mark,
                "Ctrl+Enter": self.commit,
            }
        )
        self.statusBar().addPermanentWidget(self.hints)
        self.statusBar().addPermanentWidget(self.commit_button)

        self._apply_theme()
        theme.on_change(self._apply_theme)
        self.resize(1400, 900)
        self._bind_keys()
        self._load_current()

    def _apply_theme(self) -> None:
        t = theme.current()
        self.setStyleSheet(
            f"QMainWindow {{ background: {t.background}; }}"
            f"QStatusBar {{ background: {t.status_bar}; color: {t.text}; }}"
            f"#hints QLabel {{ color: {t.text_dim}; }}"
            f'#hints QLabel[pressed="true"] {{ color: {t.text_strong}; }}'
            f"#key {{ color: {t.text}; border: 1px solid {t.key_border};"
            " border-radius: 3px; padding: 0 4px; }"
            f'#key[pressed="true"] {{ background: {t.key_border}; }}'
        )
        self.image_view.set_text_color(t.text)

    # --- actions -----------------------------------------------------------

    def next_image(self) -> None:
        if self.library.next():
            self._load_current()

    def prev_image(self) -> None:
        if self.library.prev():
            self._load_current()

    def mark_and_advance(self, mark: Mark) -> None:
        self.library.set_mark(mark)
        if self.library.next():
            self._load_current()
        else:
            self._refresh()  # last image: stay, but show the new mark

    def clear_mark(self) -> None:
        self.library.set_mark(None)
        self._refresh()

    def undo(self) -> None:
        if self.library.undo():
            self._load_current()

    def redo(self) -> None:
        if self.library.redo():
            self._load_current()

    def commit(self) -> None:
        dialog = CommitDialog(self.library, self)
        if not dialog.exec():
            return
        result = run_commit(dialog.plan(), dialog.destination)
        self.library.apply_commit(result.done)
        self._load_current()
        if result.failed:
            lines = [f"{path.name}: {error}" for path, error in result.failed[:10]]
            if len(result.failed) > 10:
                lines.append(f"…and {len(result.failed) - 10} more")
            QMessageBox.warning(
                self,
                "Commit",
                f"{len(result.failed)} files could not be moved and are still marked:\n\n"
                + "\n".join(lines),
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_hints()

    def _update_hints(self) -> None:
        """Show the shortcut hints only if they fit beside the status text."""
        bar = self.statusBar()
        text_width = bar.fontMetrics().horizontalAdvance(bar.currentMessage())
        needed = text_width + self.hints.sizeHint().width()
        needed += self.commit_button.sizeHint().width() + 40
        self.hints.setVisible(self.width() >= needed)

    # --- internals ---------------------------------------------------------

    def _bind_keys(self) -> None:
        bindings = [
            (("Right", "Space", "D"), self.next_image),
            (("Left", "A"), self.prev_image),
            (("K", "Up", "W"), lambda: self.mark_and_advance(Mark.APPROVE)),
            (("X", "Down", "S", "Delete"), lambda: self.mark_and_advance(Mark.DELETE)),
            (("R", "End", "/"), self.clear_mark),
            (("Z",), self.image_view.toggle_zoom),
            ((QKeySequence.StandardKey.Undo,), self.undo),
            ((QKeySequence.StandardKey.Redo,), self.redo),
            (("Ctrl+Return", "Ctrl+Enter"), self.commit),
        ]
        for keys, slot in bindings:
            for key in keys:
                QShortcut(QKeySequence(key), self, activated=slot)

    def _load_current(self) -> None:
        """Decode the current file from disk, then redraw."""
        path = self.library.current
        pixmap = QPixmap()
        if path is not None:
            image = load_image(path)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)

        if path is None:
            self.image_view.set_message("No images in this folder.")
        elif pixmap.isNull():
            self.image_view.set_message(f"Could not load {path.name}")
        else:
            self.image_view.set_pixmap(pixmap)  # resets zoom to fit
        self._refresh()

    def _refresh(self) -> None:
        """Update border, title and status. Leaves the image (and its zoom) alone."""
        lib = self.library
        mark = lib.current_mark
        self.image_frame.setStyleSheet(
            f"QFrame#imageFrame {{ border: {BORDER_WIDTH}px solid {BORDER_COLORS[mark]}; }}"
        )

        if lib.current is None:
            self.setWindowTitle("Plumpick")
            return

        self.setWindowTitle(f"{lib.current.name} — Plumpick")
        self._update_status()

    def _update_status(self) -> None:
        """Rewrite the status bar. Also runs on zoom changes, so it stays cheap."""
        lib = self.library
        if lib.current is None:
            return
        mark = lib.current_mark
        badge = f"  [{mark.value.upper()}]" if mark else ""
        zoom = self.image_view.zoom_percent
        self.statusBar().showMessage(
            f"{lib.index + 1} / {len(lib)}   {lib.current.relative_to(lib.root).as_posix()}{badge}"
            f"      approved {lib.count(Mark.APPROVE)}"
            f" · delete {lib.count(Mark.DELETE)}"
            f" · undecided {lib.undecided}"
            + (f"      {zoom}%" if zoom is not None else "")
        )
        self._update_hints()
