"""The image list, the cursor, and the approve/delete marks.

No Qt in this module on purpose: it is plain Python, so it is fast to test
and the UI stays a thin layer on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


class Mark(Enum):
    APPROVE = "approve"
    DELETE = "delete"


@dataclass
class Change:
    """history record for undos and redos"""

    path: Path
    mark: Mark | None


def scan_folder(folder: Path) -> list[Path]:
    """Return the images directly inside `folder`, sorted by name."""
    return sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda p: p.name.lower(),
    )


class Library:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths  # paths of all scanned images
        self.index = 0  # internal index of image
        self.marks: dict[Path, Mark] = {}  # undecided image paths are not stored
        self.undos: list[Change] = []  # TODO: history is uncapped for now
        self.redos: list[Change] = []

    @classmethod
    def from_folder(cls, folder: Path) -> Library:
        return cls(scan_folder(folder))

    def __len__(self) -> int:
        return len(self.paths)

    @property
    def current(self) -> Path | None:
        return self.paths[self.index] if self.paths else None

    @property
    def current_mark(self) -> Mark | None:
        return self.marks.get(self.current) if self.current else None

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
        return self._swap_write(self.undos, self.redos)

    def redo(self) -> bool:
        return self._swap_write(self.redos, self.undos)

    @property
    def undecided(self) -> int:
        return len(self.paths) - len(self.marks)
