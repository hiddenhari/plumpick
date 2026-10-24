"""Build the Windows installer, dist/installer/plumpick-setup-<version>.exe.

Needs Inno Setup 6 (https://jrsoftware.org/isinfo.php, or `winget install JRSoftware.InnoSetup`).
Builds dist/plumpick/ first (scripts/build.py) unless it is already there; pass --rebuild
to build it again.

Usage: uv run python scripts/build_installer.py [--rebuild]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "dist" / "plumpick"
ISS = ROOT / "installer" / "plumpick.iss"


def find_iscc() -> Path:
    on_path = shutil.which("iscc")
    if on_path:
        return Path(on_path)
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")]
    for root in filter(None, roots):
        for base in (Path(root), Path(root) / "Programs"):
            candidate = base / "Inno Setup 6" / "ISCC.exe"
            if candidate.exists():
                return candidate
    sys.exit("Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup")


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    iscc = find_iscc()
    if "--rebuild" in sys.argv or not (APP_DIR / "plumpick.exe").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True)
    subprocess.run([str(iscc), f"/DAppVersion={version}", str(ISS)], check=True)
    print(f"Wrote dist/installer/plumpick-setup-{version}.exe")


if __name__ == "__main__":
    main()
