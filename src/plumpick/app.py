"""Application entry point: pick a folder and open the cull window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog

from plumpick.cull_window import CullWindow
from plumpick.library import Library


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)

    # A folder, or an image file (e.g. from Explorer's "Open with"), which
    # opens its folder at that image.
    # TODO: every launch is a new process, so opening a second image from a
    # folder that is already open gives two windows that each overwrite
    # .plumpick.json, and the last save wins. Fix with a single instance:
    # listen on a QLocalServer; a later launch connects with a QLocalSocket,
    # sends its path to the running window, and exits.
    if len(argv) > 1:
        path = Path(argv[1])
    else:
        chosen = QFileDialog.getExistingDirectory(None, "Open image folder")
        if not chosen:
            return 0
        path = Path(chosen)

    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 1

    window = CullWindow(Library.from_path(path))
    window.show()
    return app.exec()
