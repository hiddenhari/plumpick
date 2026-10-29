"""The single-image culling window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import (
    QSizePolicy,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from plumpick import theme
from plumpick.cull.commit import run_commit
from plumpick.cull.commit_dialog import CommitDialog
from plumpick.cull.image_view import EDGE_GRADIENT_EXTRA, EDGE_WIDTH, ImageView
from plumpick.cull.library import Library, Mark
from plumpick.cull.loader import load_image

BORDER_WIDTH = 6
WIDE_BAR = 1000  # window width past which the file name is shortened, not dropped
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
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    for i, (keys, action) in enumerate(SHORTCUT_HINTS):
        if i:
            layout.addSpacing(8)
        accent = action == "commit"  # the one hint that is a big, deliberate step
        labels = [_ClickLabel(key, objectName="key") for key in keys]
        labels.append(_ClickLabel(action))
        for label, key in zip(labels, [*keys, keys[-1]]):
            label.setProperty("accent", accent)
            layout.addWidget(_clickable(label, actions[key]))
    return box


class _EdgeGradient(QWidget):
    """Transparent overlay that lets the hover gradient cover the frame border."""

    def __init__(self, parent: QWidget, image_view: ImageView) -> None:
        super().__init__(parent)
        self._image_view = image_view
        self._edge = ""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_edge(self, edge: str) -> None:
        if edge != self._edge:
            self._edge = edge
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._edge:
            return
        painter = QPainter(self)
        view = self._image_view.geometry()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._edge == "left":
            gradient_width = min(self.width(), view.x() + EDGE_WIDTH + EDGE_GRADIENT_EXTRA)
            gradient = QLinearGradient(0, 0, gradient_width, 0)
            gradient.setColorAt(0, QColor(0, 0, 0, 46))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, gradient_width, self.height(), gradient)
            center_x = view.x() + EDGE_WIDTH / 2
            direction = -1
        else:
            gradient_width = min(
                self.width(),
                self.width() - (view.x() + view.width() - EDGE_WIDTH - EDGE_GRADIENT_EXTRA),
            )
            start_x = self.width() - gradient_width
            gradient = QLinearGradient(start_x, 0, self.width(), 0)
            gradient.setColorAt(0, QColor(0, 0, 0, 0))
            gradient.setColorAt(1, QColor(0, 0, 0, 46))
            painter.fillRect(start_x, 0, gradient_width, self.height(), gradient)
            center_x = view.x() + view.width() - EDGE_WIDTH / 2
            direction = 1

        # Draw the compact left/right control on the same overlay, above the gradient.
        triangle_width = 12.0
        triangle_height = triangle_width * 1.45
        center_y = view.y() + view.height() / 2
        button_width = triangle_width + 12
        button_height = triangle_height + 20
        button_x = center_x - button_width / 2
        button_y = center_y - button_height / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.drawRoundedRect(button_x, button_y + 1, button_width, button_height, 7, 7)
        painter.setBrush(QColor(35, 35, 35, 205))
        painter.drawRoundedRect(button_x, button_y, button_width, button_height, 7, 7)
        points = QPolygonF(
            [
                QPointF(center_x + direction * triangle_width / 2, center_y),
                QPointF(center_x - direction * triangle_width / 2, center_y - triangle_height / 2),
                QPointF(center_x - direction * triangle_width / 2, center_y + triangle_height / 2),
            ]
        )
        painter.setBrush(QColor(0, 0, 0, 127))  # subtle black shadow under triangle
        painter.drawPolygon(points.translated(0, 2))
        painter.setBrush(QColor("white"))
        painter.drawPolygon(points)


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
        self.edge_overlay = _EdgeGradient(self.image_frame, self.image_view)
        self.edge_overlay.setGeometry(self.image_frame.rect())
        self.edge_overlay.raise_()
        self.image_view.zoomChanged.connect(self._update_status)
        self.image_view.edge_hover_changed.connect(self.edge_overlay.set_edge)
        self.image_view.navigate_previous.connect(self.prev_image)
        self.image_view.navigate_next.connect(self.next_image)
        self.image_view.keep_requested.connect(lambda: self._set_mark(Mark.APPROVE))
        self.image_view.reject_requested.connect(lambda: self._set_mark(Mark.DELETE))
        self.image_view.clear_mark_requested.connect(self.clear_mark)
        self.setCentralWidget(self.image_frame)

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
        # One row: status text | hints | empty. The side columns get equal width
        # (their size hints are ignored), so the hints stay centered in the window.
        self.status_label = QLabel()  # left: position, file name, zoom
        self.counts_label = QLabel(alignment=Qt.AlignmentFlag.AlignRight)  # right: tallies
        self._name_parts = ("", "", "")  # text before the file name, the name, text after
        self._counts_text = ""
        for label in (self.status_label, self.counts_label):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 0, 6, 0)
        row_layout.addWidget(self.status_label, 1)
        row_layout.addWidget(self.hints)
        row_layout.addWidget(self.counts_label, 1)
        self.statusBar().addWidget(row, 1)

        self._apply_theme()
        theme.on_change(self._apply_theme)
        self._fit_to_screen(1400, 900)
        self._bind_keys()
        self._load_current()

    def _apply_theme(self) -> None:
        t = theme.current()
        self.setStyleSheet(
            f"QMainWindow {{ background: {t.background}; }}"
            f"QStatusBar {{ background: {t.status_bar}; color: {t.text}; }}"
            f"#hints QLabel {{ color: {t.text_dim}; }}"
            f'#hints QLabel[pressed="true"] {{ color: {t.text_strong}; }}'
            f'#hints QLabel[accent="true"] {{ color: {t.text_strong}; font-weight: bold; }}'
            f"#key {{ color: {t.text}; border: 1px solid {t.key_border};"
            " border-radius: 3px; padding: 0 4px; }"
            f'#key[pressed="true"] {{ background: {t.key_border}; }}'
            f'#key[accent="true"] {{ background: {t.accent}; border-color: {t.accent};'
            " color: white; }"
            f'#key[accent="true"][pressed="true"] {{ background: {t.accent_pressed};'
            f" border-color: {t.accent_pressed}; }}"
        )
        self.image_view.set_text_color(t.text)

    # --- actions -----------------------------------------------------------

    def next_image(self) -> None:
        if self.library.next():
            self._load_current()

    def prev_image(self) -> None:
        if self.library.prev():
            self._load_current()

    def _set_mark(self, mark: Mark) -> None:
        self.library.set_mark(mark)
        self._refresh()
    
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
        self.edge_overlay.setGeometry(self.image_frame.rect())
        self.edge_overlay.raise_()
        self._update_hints()

    def _update_hints(self) -> None:
        """Lay out the status bar text around the centered hints.

        Both side columns are `side` wide. Past WIDE_BAR the left text always shows,
        with the file name shortened to fit; narrower, it shows only if it fits whole.
        The tallies on the right show only if they fit. Texts are blanked, not hidden,
        because a hidden label would leave its column and un-center the hints."""
        side = (self.width() - self.hints.sizeHint().width()) / 2 - 20
        metrics = self.status_label.fontMetrics()

        before, name, after = self._name_parts
        fixed = metrics.horizontalAdvance(before + after)
        if self.width() > WIDE_BAR:
            name = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, max(0, int(side - fixed)))
            left = before + name + after
        else:
            left = before + name + after
            if metrics.horizontalAdvance(left) > side:
                left = ""
        self.status_label.setText(left)

        fits = metrics.horizontalAdvance(self._counts_text) <= side
        self.counts_label.setText(self._counts_text if fits else "")

    # --- internals ---------------------------------------------------------

    def _fit_to_screen(self, width: int, height: int) -> None:
        """Start at width x height, but no bigger than 90% of the screen's free area,
        centered on it. On small or scaled screens a fixed size would push the
        status bar under the taskbar. The 10% leaves room for the title bar."""
        area = self.screen().availableGeometry()
        self.resize(min(width, area.width() * 9 // 10), min(height, area.height() * 9 // 10))
        self.move(area.center() - self.rect().center())

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
        self.image_view.set_has_mark(mark is not None)
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
        self._name_parts = (
            f"{lib.index + 1} / {len(lib)}   ",
            lib.current.relative_to(lib.root).as_posix(),
            badge + (f"      {zoom}%" if zoom is not None else ""),
        )
        self._counts_text = (
            f"approved {lib.count(Mark.APPROVE)}"
            f" · delete {lib.count(Mark.DELETE)}"
            f" · undecided {lib.undecided}"
        )
        self._update_hints()
