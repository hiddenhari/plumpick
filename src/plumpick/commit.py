"""Applying the marks: send deletes to the Recycle Bin or `_rejected/`.

No Qt here, same as library.py.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from send2trash import send2trash

from plumpick.library import KEPT_DIR, REJECTED_DIR, Library, Mark


class Destination(Enum):
    RECYCLE_BIN = "recycle_bin"
    REJECTED_FOLDER = "rejected_folder"


@dataclass(frozen=True)
class CommitPlan:
    root: Path
    deletes: list[Path]
    keeps: list[Path]

    @property
    def delete_bytes(self) -> int:
        total = 0
        for path in self.deletes:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return total


@dataclass
class CommitResult:
    done: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size / 1024:.1f} TB"


def plan_commit(library: Library, move_kept: bool = False) -> CommitPlan:
    def marked(mark: Mark) -> list[Path]:
        return [p for p in library.paths if library.marks.get(p) is mark]

    return CommitPlan(
        library.root, marked(Mark.DELETE), marked(Mark.APPROVE) if move_kept else []
    )


def free_path(folder: Path, name: str) -> Path:
    """`folder/name`, or `folder/stem (n).ext` if that name is taken."""
    candidate = folder / name
    stem, suffix = candidate.stem, candidate.suffix
    n = 1
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){suffix}"
        n += 1
    return candidate


def move_into(path: Path, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    shutil.move(path, free_path(folder, path.name))


def mover(root: Path, dir_name: str) -> Callable[[Path], None]:
    """Move files into `root/dir_name/`, keeping their subfolder under root,
    so `root/a/x.png` goes to `root/_rejected/a/x.png`."""
    return lambda path: move_into(path, root / dir_name / path.parent.relative_to(root))


def run_commit(
    plan: CommitPlan,
    destination: Destination,
    trash: Callable[[Path], None] = send2trash,
) -> CommitResult:
    """Apply `plan` file by file; one failure doesn't stop the rest."""
    delete = (
        trash
        if destination is Destination.RECYCLE_BIN
        else mover(plan.root, REJECTED_DIR)
    )
    keep = mover(plan.root, KEPT_DIR)

    jobs = [(p, delete) for p in plan.deletes] + [(p, keep) for p in plan.keeps]

    result = CommitResult()
    for path, action in jobs:
        try:
            action(path)
        except OSError as e:
            result.failed.append((path, str(e)))
        else:
            result.done.append(path)
    return result
