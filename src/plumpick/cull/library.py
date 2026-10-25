"""The image list, the cursor, and the approve/delete marks.

No Qt in this module on purpose: it is plain Python, so it is fast to test
and the UI stays a thin layer on top of it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
    ".heic", ".heif", ".avif", ".tif", ".tiff",
}
SAVE_FILE = ".plumpick.json"
# Where commit.py moves files. The scan skips them, or committed files would
# come back the next time the folder is opened.
REJECTED_DIR = "_rejected"
KEPT_DIR = "_kept"


class Mark(Enum):
    APPROVE = "approve"
    DELETE = "delete"


@dataclass
class Change:
    """history record for undos and redos"""

    path: Path
    mark: Mark | None


def _skip_dir(path: Path) -> bool:
    return (
        path.name in (REJECTED_DIR, KEPT_DIR)
        or path.name.startswith(".")
        or path.is_symlink()
        or path.is_junction()  # Windows directory links, which could loop
    )


def scan_folder(folder: Path) -> list[Path]:
    """Return the images in `folder` and its subfolders.

    Each folder's images come sorted by name, before its subfolders' images,
    which follow in name order. Commit output (`_rejected/`, `_kept/`),
    hidden folders and links are skipped. Unreadable folders are skipped
    silently by os.walk.
    """
    images: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(folder):
        here = Path(dirpath)
        dirnames[:] = sorted(
            (d for d in dirnames if not _skip_dir(here / d)), key=str.lower
        )
        images.extend(
            here / name
            for name in sorted(filenames, key=str.lower)
            if Path(name).suffix.lower() in IMAGE_EXTENSIONS
        )
    return images


class Library:
    def __init__(self, root: Path, paths: list[Path]) -> None:
        self.root = root
        self.paths = paths  # paths of all scanned images
        self.index = 0  # internal index of image
        self.marks: dict[Path, Mark] = {}  # undecided image paths are not stored
        self.undos: list[Change] = []  # TODO: history is uncapped for now
        self.redos: list[Change] = []

    @classmethod
    def from_folder(cls, folder: Path, start: Path | None = None) -> Library:
        """Scan `folder` and resume its session. If `start` names one of its
        images, begin there instead of at the saved index."""
        library = cls(folder, scan_folder(folder))
        library.load_session()
        if start is not None:
            library.goto_path(start)
        return library

    @classmethod
    def from_path(cls, path: Path) -> Library:
        """Open a folder, or the folder containing an image file at that image."""
        path = path.absolute()
        if path.is_file():
            return cls.from_folder(path.parent, start=path)
        return cls.from_folder(path)

    def __len__(self) -> int:
        return len(self.paths)

    @property
    def current(self) -> Path | None:
        return self.paths[self.index] if self.paths else None

    @property
    def current_mark(self) -> Mark | None:
        return self.marks.get(self.current) if self.current else None

    @property
    def session_file(self) -> Path:
        return self.root / SAVE_FILE

    def save_session(self) -> None:
        data = {
            "version": 1,
            "index": self.index,
            "marks": {
                # relative, so the session survives moving the folder
                path.relative_to(self.root).as_posix(): mark.value
                for path, mark in self.marks.items()
            },
        }
        temp_path = self.session_file.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
            os.replace(temp_path, self.session_file)
        finally:
            temp_path.unlink(missing_ok=True)

    def load_session(self) -> None:
        """Restore index and marks for the already-scanned `self.paths`."""
        known = set(self.paths)
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            index = int(data["index"])
            marks = {}
            for rel, mark in data["marks"].items():
                path = self.root / rel
                if path in known:  # missing files are dropped
                    marks[path] = Mark(mark)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return  # missing or corrupt session: start fresh

        self.marks = marks
        self.index = min(max(index, 0), len(self.paths) - 1) if self.paths else 0

    def next(self) -> bool:
        """Move to the next image. Returns False if already at the end."""
        if self.index + 1 >= len(self.paths):
            return False
        self.index += 1
        return True

    def prev(self) -> bool:
        """Move to the previous image. Returns False if already at the start."""
        if self.index == 0:
            return False
        self.index -= 1
        return True

    def goto(self, index: int) -> bool:
        if index < 0 or index >= len(self.paths):
            return False
        self.index = index
        return True

    def goto_path(self, target: Path) -> bool:
        """Move to this image (case-insensitive on Windows)."""
        wanted = os.path.normcase(target)
        for i, path in enumerate(self.paths):
            if os.path.normcase(path) == wanted:
                self.index = i
                return True
        return False

    def _write_mark(self, path: Path, mark: Mark | None) -> None:
        if mark is None:
            self.marks.pop(path, None)
        else:
            self.marks[path] = mark

    def set_mark(self, mark: Mark | None) -> None:
        """Mark the current image; `None` clears the mark."""
        if self.current is None or mark is self.current_mark:
            return
        self.undos.append(Change(self.current, self.current_mark))
        self.redos.clear()
        self._write_mark(self.current, mark)
        self.save_session()  # TODO: measure performance, maybe debounce

    def count(self, mark: Mark) -> int:
        return sum(1 for m in self.marks.values() if m is mark)

    def _swap_write(self, from_stack: list[Change], to_stack: list[Change]) -> bool:
        """helper for undo and redo, same logic but reverse"""
        if not from_stack:
            return False

        # each undo/redo swap the history record to other's stack
        change = from_stack.pop()
        to_stack.append(Change(change.path, self.marks.get(change.path)))
        self._write_mark(change.path, change.mark)

        try:
            self.index = self.paths.index(change.path)
        except ValueError:
            pass  # not in the current list e.g. filtered out
        return True

    def undo(self) -> bool:
        if not self._swap_write(self.undos, self.redos):
            return False
        self.save_session()
        return True

    def redo(self) -> bool:
        if not self._swap_write(self.redos, self.undos):
            return False
        self.save_session()
        return True

    def apply_commit(self, removed: Iterable[Path]) -> None:
        """Forget files that a commit moved away, then go to the first undecided."""
        gone = set(removed)
        self.paths = [p for p in self.paths if p not in gone]
        self.marks = {p: m for p, m in self.marks.items() if p not in gone}
        self.undos.clear()  # moved files can't be un-marked back into place
        self.redos.clear()
        self.index = next(
            (i for i, p in enumerate(self.paths) if p not in self.marks), 0
        )
        self.save_session()

    @property
    def undecided(self) -> int:
        return len(self.paths) - len(self.marks)
