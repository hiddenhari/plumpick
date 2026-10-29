"""Application entry point: pick a folder and open the cull window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from plumpick.app.app_menu import (
    load_recent_folders,
    normalize_folder,
    remember_folder,
)
from plumpick.app.welcome import WelcomeWindow
from plumpick.cull.cull_window import CullWindow
from plumpick.cull.library import Library, ScanError

ICON = Path(__file__).parent.parent / "assets" / "plumpick.ico"
MAX_OPEN_CULL_WINDOWS = 8


def _track_window(windows: list[QMainWindow], window: QMainWindow) -> None:
    """Keep live top-level windows reachable, then forget them on close."""
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window_id = id(window)

    def forget_closed_window(*_args) -> None:
        windows[:] = [candidate for candidate in windows if id(candidate) != window_id]

    window.destroyed.connect(forget_closed_window)
    windows.append(window)


def _close_oldest_cull_window(windows: list[QMainWindow]) -> bool:
    """Retire the oldest culling window before opening another past the cap."""
    open_windows = [
        window
        for window in windows
        if isinstance(window, CullWindow)
        and not window.property("_plumpick_closing")
    ]
    if len(open_windows) < MAX_OPEN_CULL_WINDOWS:
        return True

    oldest = open_windows[0]
    oldest.setProperty("_plumpick_closing", True)
    if oldest.close():
        return True
    oldest.setProperty("_plumpick_closing", False)
    return False


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    _set_app_id()
    app = QApplication(argv)
    app.setWindowIcon(QIcon(str(ICON)))

    # A folder, or an image file (e.g. from Explorer's "Open with"), which
    # opens its folder at that image.
    # TODO: another process can still open this same folder and overwrite its
    # .plumpick.json. A single-instance QLocalServer would route that path here.
    windows: list[QMainWindow] = []

    def open_path(path: Path) -> bool:
        candidate = path.parent if path.is_file() else path
        requested = normalize_folder(candidate).casefold()
        for existing in windows:
            if isinstance(existing, CullWindow) and not existing.property(
                "_plumpick_closing"
            ):
                if normalize_folder(existing.library.root).casefold() == requested:
                    existing.showNormal()
                    existing.raise_()
                    existing.activateWindow()
                    return True
        try:
            library = Library.from_path(path)
        except ScanError as error:
            QMessageBox.warning(None, "plumpick", str(error))
            return False
        if not _close_oldest_cull_window(windows):
            return False
        window = CullWindow(
            library, open_folder=open_path, recent_folders=load_recent_folders
        )
        remember_folder(library.root)
        _track_window(windows, window)
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
        _track_window(windows, welcome)
        welcome.show()
    return app.exec()


def _set_app_id() -> None:
    """Run from source, the process is python.exe, and the taskbar would group
    the window under Python with Python's icon. Its own app ID gives it its own
    taskbar button with the window icon. The built exe doesn't need this."""
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("plumpick")
