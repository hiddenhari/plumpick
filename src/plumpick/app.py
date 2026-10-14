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

    if len(argv) > 1:
        folder = Path(argv[1])
    else:
        chosen = QFileDialog.getExistingDirectory(None, "Open image folder")
        if not chosen:
            return 0
        folder = Path(chosen)

    if not folder.is_dir():
        print(f"Not a folder: {folder}", file=sys.stderr)
        return 1

    window = CullWindow(Library.from_folder(folder))
    window.show()
    return app.exec()
