"""The single-image culling window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QKeySequence, QPixmap, QResizeEvent, QShortcut
from PySide6.QtWidgets import QLabel, QMainWindow, QSizePolicy

from plumpick.library import Library, Mark

BORDER_WIDTH = 6
BORDER_COLORS = {Mark.APPROVE: "#3fb950", Mark.DELETE: "#f85149", None: "transparent"}


class CullWindow(QMainWindow):
    def __init__(self, library: Library) -> None:
        super().__init__()
        self.library = library
        self._pixmap = QPixmap()  # full-size image; scaled copies are made on resize

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        # Ignored: the pixmap must not dictate the label's size, or the window
        # grows to fit every large image and resizing would feed back on itself.
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setCentralWidget(self.image_label)

        self.setStyleSheet("QMainWindow { background: #1e1e1e; } QLabel { color: #ccc; }")
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

    # --- internals ---------------------------------------------------------

    def _bind_keys(self) -> None:
        bindings = [
            (("Right", "Space"), self.next_image),
            (("Left",), self.prev_image),
            (("K", "Up"), lambda: self.mark_and_advance(Mark.APPROVE)),
            (("X", "Down", "Delete"), lambda: self.mark_and_advance(Mark.DELETE)),
            (("U",), self.clear_mark),
        ]
        for keys, slot in bindings:
            for key in keys:
                QShortcut(QKeySequence(key), self, activated=slot)

    def _load_current(self) -> None:
        """Decode the current file from disk, then redraw."""
        path = self.library.current
        self._pixmap = QPixmap()
        if path is not None:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)  # respect EXIF rotation
            image = reader.read()
            if not image.isNull():
                self._pixmap = QPixmap.fromImage(image)
        self._refresh()

    def _refresh(self) -> None:
        """Redraw from the already-loaded pixmap (cheap; no disk access)."""
        lib = self.library
        mark = lib.current_mark
        self.image_label.setStyleSheet(
            f"QLabel {{ border: {BORDER_WIDTH}px solid {BORDER_COLORS[mark]}; }}"
        )

        if lib.current is None:
            self.image_label.setText("No images in this folder.")
            self.setWindowTitle("Plumpick")
            return

        if self._pixmap.isNull():
            self.image_label.setText(f"Could not load {lib.current.name}")
        else:
            self.image_label.setPixmap(
                self._pixmap.scaled(
                    self.image_label.contentsRect().size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        badge = f"  [{mark.value.upper()}]" if mark else ""
        self.setWindowTitle(f"{lib.current.name} — Plumpick")
        self.statusBar().showMessage(
            f"{lib.index + 1} / {len(lib)}   {lib.current.name}{badge}"
            f"      approved {lib.count(Mark.APPROVE)}"
            f" · delete {lib.count(Mark.DELETE)}"
            f" · undecided {lib.undecided}"
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh()
