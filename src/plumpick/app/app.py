"""Application entry point: pick a folder and open the cull window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from plumpick.app.welcome import WelcomeWindow
from plumpick.cull.cull_window import CullWindow
from plumpick.cull.library import Library, ScanError

ICON = Path(__file__).parent.parent / "assets" / "plumpick.ico"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    _set_app_id()
    app = QApplication(argv)
    app.setWindowIcon(QIcon(str(ICON)))

    # A folder, or an image file (e.g. from Explorer's "Open with"), which
    # opens its folder at that image.
    # TODO: every launch is a new process, so opening a second image from a
    # folder that is already open gives two windows that each overwrite
    # .plumpick.json, and the last save wins. Fix with a single instance:
    # listen on a QLocalServer; a later launch connects with a QLocalSocket,
    # sends its path to the running window, and exits.
    windows: list[QMainWindow] = []

    def open_path(path: Path) -> bool:
        try:
            library = Library.from_path(path)
        except ScanError as error:
            QMessageBox.warning(None, "plumpick", str(error))
            return False
        window = CullWindow(library)
        windows.append(window)
        window.show()
        return True

    if len(argv) > 1:
        path = Path(argv[1])
        if not path.exists():
            print(f"Not found: {path}", file=sys.stderr)
            return 1
        if not open_path(path):
            return 1
    else:
        welcome = WelcomeWindow()

        def on_chosen(path: Path) -> None:
            if open_path(path):
                welcome.close()

        welcome.pathChosen.connect(on_chosen)
        windows.append(welcome)
        welcome.show()
    return app.exec()


def _set_app_id() -> None:
    """Run from source, the process is python.exe, and the taskbar would group
    the window under Python with Python's icon. Its own app ID gives it its own
    taskbar button with the window icon. The built exe doesn't need this."""
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("plumpick")
