# Plumpick

Fast keep/delete culling for large batches of generated images. Open a folder, press a key per image, move on.

**Status: early WIP (roughly milestone M1).** The roadmap is in [PLAN.md](PLAN.md). This is a personal hobby project, built in Python through M4, then re-assessed (a Rust or C++ rewrite is possible).

## Current state

- Open a folder (pass it on the command line, or pick it in a dialog). Images in it and its subfolders are listed: each folder's images sorted by name, then its subfolders in name order. `_rejected/`, `_kept/`, hidden folders and links are skipped. The status bar shows the path relative to the opened folder.
- Open an image file instead, and its folder opens at that image. On Windows, right-click an image → **Open with** → **Choose another app** → browse to `plumpick.exe`; after that Plumpick stays in the Open with list.
- View one image at a time, scaled to fit the window, with EXIF rotation applied.
- Mark each image as approve or delete. The image gets a green or red border, and the status bar shows the position, filename, and counts of approved, delete and undecided images.
- Undo / redo of marks.
- Decisions are saved to `.plumpick.json` in the folder as you go, so reopening the folder resumes where you left off.
- Commit (`Ctrl+Enter` or the **Commit…** button): files marked for delete go to the Recycle Bin or a `_rejected/` subfolder (the last choice is remembered), and approved files can optionally be moved to `_kept/`. Files from subfolders keep their subfolder inside those (`a/x.png` → `_rejected/a/x.png`). Existing files are never overwritten. Afterwards the view jumps to the first undecided image. Commit can't be undone from the app, but nothing is permanently deleted.
- Supported: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`.

| Key | Action |
|---|---|
| `→` / `Space` | next image |
| `←` | previous image |
| `K` / `↑` | approve, then next |
| `X` / `↓` / `Delete` | mark for delete, then next |
| `U` | clear the mark |
| `Ctrl+Z` / `Ctrl+Y` | undo / redo |
| `Ctrl+Enter` | commit |

## WIP

- Background prefetch and an image cache. Each image is currently decoded from disk when you navigate to it.
- Thumbnail grid and filmstrip~~, with filters~~.
- Zoom, remappable shortcuts, drag-and-drop, recent folders.
- AVIF support.


## Requirements

- Python 3.14 (see `.python-version`) and [uv](https://docs.astral.sh/uv/)
- Windows is the development platform. Linux and macOS are untested.
- Runtime dependencies (installed by uv): `pyside6-essentials`, `pillow`, `send2trash`. *`pillow` is declared but not used by the code yet.*

## Setup on a new machine

```sh
git clone https://github.com/hiddenhari/plumpick.git
cd plumpick
uv sync          # creates .venv with the right Python and all dependencies, including pytest
```

If uv can't find Python 3.14 it will download it. If PySide6 has no wheel for your Python version, change `requires-python` in `pyproject.toml` and the version in `.python-version` to one it supports.

## Run

```sh
uv run plumpick                    # opens a folder picker
uv run plumpick path/to/images     # opens that folder directly
uv run python -m plumpick path/to/images   # equivalent
uv run plumpick path/to/images/0042.png    # opens that folder at 0042.png
```

## Build an exe

```sh
uv run python scripts/build.py
```

This writes `dist/plumpick/`, about 100 MB, containing `plumpick.exe` and an `_internal/` folder. Ship the whole folder (zip it); the exe doesn't run on its own. Users don't need Python installed. Drag a folder or an image onto `plumpick.exe` to open it, or run the exe to get a folder picker.

The app icon is `src/plumpick/assets/plumpick.ico`, built from the pixel-art `assets/plum.png`, scaled with nearest-neighbour so it stays crisp. After changing the PNG, regenerate it with `uv run python scripts/make_icon.py` and commit the `.ico`; the build uses it as is.

## Build an installer

```sh
winget install JRSoftware.InnoSetup    # once
uv run python scripts/build_installer.py
```

This builds `dist/plumpick/` if needed, then writes `dist/installer/plumpick-setup-<version>.exe` (the version comes from `pyproject.toml`). The installer is per-user by default (no admin prompt, installs to `%LOCALAPPDATA%\Programs\plumpick`) and offers an all-users install. It adds a Start menu entry, optional desktop shortcut, plumpick in the "Open with" list for images, and an optional "Open with plumpick" entry in the folder right-click menu. It shows up in Settings > Apps, and uninstalling removes the files, shortcuts and registry keys. The `.plumpick.json` files inside your image folders are not touched. The installer is unsigned, so Windows SmartScreen may warn on first run. Settings are in `installer/plumpick.iss`; its `AppId` must never change, since it is how upgrades and uninstall find the install.

## Release

Releases are built by GitHub Actions ([.github/workflows/release.yml](.github/workflows/release.yml)). To publish one:

1. Bump `version` in `pyproject.toml` (`uv version --bump minor`, or `patch`), commit and push.
2. Tag that commit with the same version and push the tag:
   ```sh
   git tag v0.2.0
   git push origin v0.2.0
   ```

The workflow checks the tag matches `pyproject.toml`, runs the tests, builds the exe on Windows, and publishes a GitHub Release with `plumpick-v0.2.0-windows-x64.zip` attached. Progress is in the repo's **Actions** tab. If it fails, fix the problem, then delete and re-push the tag (`git tag -d v0.2.0 && git push origin :v0.2.0`).

## Test

```sh
uv run pytest            # run everything
uv run pytest -v         # list each test
uv run pytest -k undo    # only tests with "undo" in the name
uv run pytest -x --pdb   # stop at the first failure and drop into the debugger
```

The tests cover `library.py` and `commit.py`, which have no Qt code, so they run without a display. There are no UI tests yet.

## Layout

```
src/plumpick/
  __main__.py          # python -m plumpick
  app/                 # startup: what to open
    app.py             # QApplication setup, folder/file choice, opens the window
    welcome.py         # the window that offers to open an image or a folder
  cull/                # the culling itself
    library.py         # image list, cursor, marks, undo/redo (plain Python, no Qt)
    commit.py          # applying marks: Recycle Bin / _rejected/ / _kept/ (plain Python, no Qt)
    commit_dialog.py   # the confirm dialog before a commit
    cull_window.py     # the single-image window and key bindings
    image_view.py      # the zoom/pan image widget
  assets/plumpick.ico  # app icon, generated by scripts/make_icon.py from assets/plum.png
installer/plumpick.iss  # Inno Setup script for the Windows installer
scripts/                # build.py (exe), build_installer.py, make_icon.py
tests/
  test_library.py
  test_commit.py
  test_image_view.py
```

`library.py` and `commit.py` have no Qt imports on purpose: it is easy to test, and the UI stays a thin layer on top of it.
