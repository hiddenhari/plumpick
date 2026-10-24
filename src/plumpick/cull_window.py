"""The single-image culling window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QFrame, QMainWindow, QMessageBox, QPushButton, QVBoxLayout

from plumpick.commit import run_commit
from plumpick.commit_dialog import CommitDialog
from plumpick.image_view import ImageView
from plumpick.library import Library, Mark

BORDER_WIDTH = 6
BORDER_COLORS = {Mark.APPROVE: "#3fb950", Mark.DELETE: "#f85149", None: "transparent"}


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

        commit_button = QPushButton("Commit…", clicked=self.commit)
        commit_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep Space for navigation
        self.statusBar().addPermanentWidget(commit_button)

        self.setStyleSheet("QMainWindow { background: #1e1e1e; }")
        self.resize(1200, 800)
        self._bind_keys()
        self._load_current()

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
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)  # respect EXIF rotation
            image = reader.read()
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
