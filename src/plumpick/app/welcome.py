"""Welcome screen shown when plumpick is launched without a path."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plumpick import theme
from plumpick.cull.library import IMAGE_EXTENSIONS


class WelcomeWindow(QMainWindow):
    """Offers to open a folder, or takes a dropped image (or folder)."""

    pathChosen = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("plumpick")
        self.setAcceptDrops(True)

        title = QLabel("plumpick", objectName="title")
        hint = QLabel("Drop an image or folder here\nor", objectName="hint")
        for label in (title, hint):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button = QPushButton("Open folder…", clicked=self._choose_folder)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(panel)

        self._apply_theme()
        theme.on_change(self._apply_theme)
        self.resize(560, 360)

    def _apply_theme(self) -> None:
        t = theme.current()
        self.setStyleSheet(
            f"QMainWindow, QWidget {{ background: {t.background}; color: {t.text}; }}"
            f"#title {{ font-size: 32px; color: {t.text_strong}; }}"
            "#hint { font-size: 15px; }"
            f"QPushButton {{ padding: 8px 20px; background: {t.status_bar};"
            f" border: 1px solid {t.key_border}; border-radius: 3px; }}"
            f"QPushButton:pressed {{ background: {t.key_border}; color: {t.text_strong}; }}"
        )

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Open image folder")
        if chosen:
            self.pathChosen.emit(Path(chosen))

    @staticmethod
    def _droppable(event) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if path.is_dir() or path.suffix.lower() in IMAGE_EXTENSIONS:
            return path
        return None

    def dragEnterEvent(self, event) -> None:
        if self._droppable(event):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        path = self._droppable(event)
        if path:
            event.acceptProposedAction()
            self.pathChosen.emit(path)
