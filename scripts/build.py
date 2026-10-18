"""Build the Windows app into dist/plumpick/ with PyInstaller.

Usage: uv run python scripts/build.py
"""

from __future__ import annotations

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    PyInstaller.__main__.run(
        [
            str(ROOT / "src" / "plumpick" / "__main__.py"),
            "--name=plumpick",
            "--onedir",  # starts faster than --onefile, which unpacks to a temp dir on every launch
            "--windowed",  # no console window
            "--noconfirm",
            "--clean",
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build'}",
            f"--specpath={ROOT / 'build'}",
            f"--paths={ROOT / 'src'}",
        ]
    )


if __name__ == "__main__":
    main()
