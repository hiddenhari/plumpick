"""Build the Windows app into dist/plumpick/ with PyInstaller.

Usage: uv run python scripts/build.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "src" / "plumpick" / "assets" / "plumpick.ico"
OUT_DIR = ROOT / "dist" / "plumpick"


def running_from_dist() -> list[str]:
    """Processes started from the previous build. Windows won't let PyInstaller
    delete the files they have open, and its error doesn't say why."""
    if sys.platform != "win32":
        return []
    script = (
        r"Get-Process | Where-Object { $_.Path -like $env:PLUMPICK_OUT + '\*' } "
        "| ForEach-Object { \"$($_.Name) (PID $($_.Id))\" }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PLUMPICK_OUT": str(OUT_DIR)},
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    running = running_from_dist()
    if running:
        sys.exit(f"Close these first, they are running from {OUT_DIR}: {', '.join(running)}")
    try:
        build()
    except PermissionError as error:
        sys.exit(
            f"{error}\n"
            f"Something still has files in {OUT_DIR} open: close Explorer windows "
            "or terminals there, or wait a moment for antivirus to finish scanning, then retry."
        )


def build() -> None:
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
            f"--icon={ICON}",  # the exe's icon in Explorer, Open with and the taskbar
            # The same file for the window icon, at plumpick/assets/ like in the source tree.
            f"--add-data={ICON}{os.pathsep}plumpick/assets",
        ]
    )


if __name__ == "__main__":
    main()
