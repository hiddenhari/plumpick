# Plumpick — Development Plan

A fast desktop app for sorting large batches of **generated images** (Stable Diffusion / ComfyUI / Midjourney exports, renders, etc.) into *keep* and *delete* with as few keystrokes as possible.

## 1. Goals

- Open a folder of 1,000–50,000 images and start sorting in under 2 seconds.
- Sort each image with one keypress. Moving to the next image should feel instant (<50 ms).
- Make deletes safe: nothing is permanently removed. Every decision can be undone until you commit.
- Show what makes generated images different: prompt, seed, model, and workflow metadata embedded in the file.

**Not goals (for now):** editing images, camera RAW/EXIF workflows, cloud sync, or tagging and catalog management like Lightroom.

## 2. Core workflow

1. **Open folder** (drag-and-drop or a dialog; it remembers recent folders).
2. **Cull view:** one big image, filmstrip at the bottom, status bar showing `kept / deleted / remaining`.
3. Press a key for each image:
   | Key | Action |
   |---|---|
   | `→` / `Space` | next (leaves it undecided) |
   | `←` | previous |
   | `K` / `↑` | keep, then go to next |
   | `X` / `↓` / `Del` | mark for delete, then go to next |
   | `U` | clear the mark |
   | `Ctrl+Z` / `Ctrl+Y` | undo / redo |
   | `G` | toggle grid view |
   | `I` | toggle metadata panel |
   | `Z` / scroll | zoom 100% / fit |
   | `1`–`5` | optional star rating |
4. **Grid view:** a zoomable thumbnail grid for spotting obvious rejects in bulk. You can multi-select (shift/ctrl/rubber-band) and mark them all at once.
5. **Commit:** a review screen lists the files marked for delete. You choose one of:
   - **Recycle Bin** (default, via `send2trash`)
   - **Move to `_rejected/` subfolder**
   - optionally, **move kept files to `_kept/`**
6. **Session persistence:** decisions are saved to `.plumpick.json` in the folder as you go, so closing and reopening resumes where you left off.

## 3. Generated-image specifics

- **Metadata panel** that parses:
  - A1111 / Forge: PNG `parameters` text chunk (prompt, negative, steps, sampler, seed, model)
  - ComfyUI: PNG `prompt` / `workflow` JSON chunks (prompt text from the CLIP nodes, seed, checkpoint)
  - Plain EXIF / XMP / WebP and JPEG comments as a fallback
- **Copy prompt / copy seed** buttons.
- **Group by batch:** cluster images that share a prompt (or have near-identical metadata) so you compare variants side by side.
- **Compare mode** (later): 2–4 images side by side, keep the best and reject the rest with one key.
- **Duplicate / near-duplicate detection** (later): perceptual hash (`imagehash`) to flag near-identical outputs.

## 4. Architecture

```
plumpick/
  pyproject.toml
  src/plumpick/
    __main__.py          # entry point: python -m plumpick
    app.py               # QApplication setup, main window
    model/
      library.py         # scans folder, holds ImageItem list + decisions
      decisions.py       # keep/delete state, undo/redo stack, JSON session file
      metadata.py        # A1111 / ComfyUI / EXIF parsers
    io/
      loader.py          # background decode + LRU image cache, prefetch ±N
      thumbs.py          # thumbnail generation + disk cache
      commit.py          # recycle / move operations, with a dry-run list
    ui/
      main_window.py
      cull_view.py       # single-image viewer (QGraphicsView, zoom/pan)
      grid_view.py       # QListView in IconMode + custom delegate
      filmstrip.py
      metadata_panel.py
      commit_dialog.py
      shortcuts.py       # central, user-remappable key map
  tests/
```

**Key technical decisions**

| Concern | Choice | Why |
|---|---|---|
| GUI | **PySide6 (Qt 6)** | Native, GPU-friendly image drawing, mature model/view widgets for big grids, LGPL |
| Decoding | `QImageReader` (JPEG/PNG/WebP), Pillow as fallback (AVIF etc.) | `QImageReader.setScaledSize` decodes JPEG at reduced size, which is very fast |
| Speed | `QThreadPool` workers + LRU cache (~300 MB); prefetch the next 5 and previous 2 images | Next image is already decoded when you press the key |
| Thumbnails | 256 px WebP stored in `%LOCALAPPDATA%/plumpick/thumbs`, keyed by path+mtime+size | Grid of 10k images loads instantly the second time |
| Large folders | Lazy model: the scan lists only filenames and stats; decoding happens on demand | Opening is O(listdir) |
| Safe delete | `send2trash` | Recycle Bin on Windows and the platform trash elsewhere |
| Persistence | `.plumpick.json` per folder + `QSettings` for app preferences | Plain text, portable, easy to inspect |
| Packaging | PyInstaller (one-folder build) → later an Inno Setup installer | Single double-click exe |
| Tooling | `uv` for env/deps, `ruff` for linting, `pytest` + `pytest-qt` for tests | |

### Toolchain on the dev machine

- Python 3.14
- Visual Studio Community 2026: MSVC 14.44 / 14.51, CMake 4.3.1, and Ninja (bundled under `Common7\IDE\CommonExtensions\Microsoft\CMake`). These are **not on PATH**, so use a *Developer PowerShell for VS 2026* window or call `vcvars64.bat` first.
- No Node or Rust, and Qt for C++ is not installed.

### Alternative stack: native C++ (if Python is ruled out)

| Option | Pros | Cons |
|---|---|---|
| **A. Python + PySide6** (current plan) | Fastest to build and iterate. Qt already decodes and draws in C++, so it's fast where it matters. | ~150 MB bundled build, ~1 s startup |
| **B. C++ / Qt 6 / CMake** | Same design as A, small fast exe | Needs a Qt install (online installer, or a ~1 h vcpkg build), slower to iterate |
| **C. C++ / SDL3 + Dear ImGui / CMake** | Tiny exe, starts instantly, full GPU control, all dependencies via `FetchContent` (stb_image / libspng / libjpeg-turbo / libwebp) | Grid view, text panels, and file dialogs have to be built by hand. Most work. |

Recommendation: start with **A**. If profiling shows the Python layer is a bottleneck, move the hot paths (decode, thumbnailing, perceptual hashing) into a small C++ extension built with CMake + nanobind. That keeps the UI in Python.

## 5. Milestones

**M0 — Skeleton (½ day)**
- `pyproject.toml`, venv, PySide6 installed, an empty window launches with `python -m plumpick`.
- ruff + pytest set up, git repo.

**M1 — MVP culling (2–3 days)** ← *usable from here on*
- Open folder → recursive scan of jpg/png/webp/avif.
- Cull view with fit-to-window, keyboard navigation, keep/delete marks shown as a colored border plus a badge.
- Background prefetch + LRU cache.
- Undo/redo.
- Session file auto-save and resume.
- Commit dialog → Recycle Bin or `_rejected/` folder.

**M2 — Grid & filmstrip (2 days)**
- Thumbnail worker + disk cache.
- Grid view with adjustable thumbnail size, multi-select, bulk mark.
- Filmstrip in cull view.
- Filter: show all / undecided / kept / deleted.

**M3 — Generated-image metadata (1–2 days)**
- A1111 + ComfyUI parsers with unit tests on sample files.
- Metadata side panel, copy prompt/seed.
- Sort by name / date / seed / prompt; group by prompt.

**M4 — Polish (2 days)**
- Zoom/pan at 100%, and a hold-key peek at 100%.
- Configurable shortcuts, dark theme.
- Drag-and-drop folders, recent folders.
- Stats: “312 kept / 1,840 deleted, 4.2 GB freed”.

**M5 — Power features (optional)**
- Compare mode (2–4 up).
- Near-duplicate detection with perceptual hash.
- Auto-advance timer / “slideshow cull”.
- Watch the folder for new images while a generator is running (live culling of a ComfyUI output dir).
- On-screen buttons for each shortcut (prev / next / approve / delete / clear / undo / redo) in a bottom toolbar next to Commit. Build them from `QAction`s that own the shortcuts, so keys, buttons and tooltips share one list. Buttons must be `NoFocus` so `Space` keeps navigating.

**M6 — Distribution**
- PyInstaller build script, app icon, Inno Setup installer, GitHub release.

## 6. Performance targets & how to verify

- Generate a test set: `scripts/make_fixtures.py` writes N synthetic PNG/JPEGs with fake A1111/ComfyUI metadata.
- Benchmarks: time to first image on 20k files; next-image latency with prefetch (p95 < 50 ms on 1024² PNG); memory ceiling stays under the cache limit.
- `pytest-qt` tests for the keyboard flow: open → mark → undo → commit (into a temp dir, checking that files ended up in `_rejected/`).

## 7. Risks

- **Big PNGs decode slowly** (2–4K upscales): mitigate with decode-at-screen-size and deeper prefetch.
- **Deleting by accident:** never delete outright; use the Recycle Bin by default, require a commit step, and keep a session log.
- **ComfyUI metadata varies** from workflow to workflow: parse it as best we can and always show the raw JSON as a fallback.
- **Python 3.14 wheels:** confirm that PySide6 / Pillow ship 3.14 wheels; if not, pin a 3.12/3.13 venv via `uv`.

## 8. Open questions

- Should commit happen per session, or should each delete apply immediately (to the Recycle Bin)?
- Are star ratings / color labels useful, or is it strictly binary keep/delete?
- Should video outputs (mp4/webm from generators) be in scope?
