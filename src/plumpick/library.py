"""The image list, the cursor, and the approve/delete marks.

No Qt in this module on purpose: it is plain Python, so it is fast to test
and the UI stays a thin layer on top of it.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


class Mark(Enum):
    APPROVE = "approve"
    DELETE = "delete"


def scan_folder(folder: Path) -> list[Path]:
    """Return the images directly inside `folder`, sorted by name."""
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


class Library:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths
        self.index = 0
        self.marks: dict[Path, Mark] = {}

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

    def set_mark(self, mark: Mark | None) -> None:
        """Mark the current image; `None` clears the mark."""
        if self.current is None:
            return
        if mark is None:
            self.marks.pop(self.current, None)
        else:
            self.marks[self.current] = mark

    def count(self, mark: Mark) -> int:
        return sum(1 for m in self.marks.values() if m is mark)

    @property
    def undecided(self) -> int:
        return len(self.paths) - len(self.marks)
