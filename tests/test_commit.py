from pathlib import Path

import pytest

from plumpick.cull.commit import (
    KEPT_DIR,
    REJECTED_DIR,
    Destination,
    format_bytes,
    plan_commit,
    run_commit,
)
from plumpick.cull.library import Library, Mark, scan_folder


def make_marked_library(root: Path, marks: list[Mark | None]) -> Library:
    for i in range(len(marks)):
        (root / f"img{i}.png").write_bytes(b"x" * (i + 1))
    lib = Library.from_folder(root)
    for path, mark in zip(lib.paths, marks):
        if mark is not None:
            lib.marks[path] = mark
    return lib


class FakeTrash:
    def __init__(self, fail: set[str] = frozenset()) -> None:
        self.trashed: list[Path] = []
        self.fail = fail

    def __call__(self, path: Path) -> None:
        if Path(path).name in self.fail:
            raise OSError("access denied")
        self.trashed.append(Path(path))


def test_plan_lists_deletes_in_library_order(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE, Mark.APPROVE, None, Mark.DELETE])
    plan = plan_commit(lib)
    assert plan.deletes == [tmp_path / "img0.png", tmp_path / "img3.png"]
    assert plan.keeps == []


def test_plan_includes_keeps_only_when_asked(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.APPROVE, Mark.DELETE, Mark.APPROVE])
    plan = plan_commit(lib, move_kept=True)
    assert plan.keeps == [tmp_path / "img0.png", tmp_path / "img2.png"]


def test_plan_delete_bytes_skips_missing_files(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE, Mark.DELETE, Mark.DELETE])
    (tmp_path / "img1.png").unlink()
    assert plan_commit(lib).delete_bytes == 1 + 3


def test_recycle_bin_trashes_each_delete(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE, Mark.APPROVE, Mark.DELETE])
    trash = FakeTrash()
    result = run_commit(plan_commit(lib), Destination.RECYCLE_BIN, trash=trash)

    assert trash.trashed == [tmp_path / "img0.png", tmp_path / "img2.png"]
    assert result.done == trash.trashed
    assert result.failed == []


def test_rejected_folder_moves_deletes(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE, None])
    result = run_commit(plan_commit(lib), Destination.REJECTED_FOLDER)

    assert not (tmp_path / "img0.png").exists()
    assert (tmp_path / REJECTED_DIR / "img0.png").read_bytes() == b"x"
    assert (tmp_path / "img1.png").exists()
    assert result.done == [tmp_path / "img0.png"]


def test_move_never_overwrites_existing_file(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE])
    rejected = tmp_path / REJECTED_DIR
    rejected.mkdir()
    (rejected / "img0.png").write_bytes(b"old")
    (rejected / "img0 (1).png").write_bytes(b"older")

    run_commit(plan_commit(lib), Destination.REJECTED_FOLDER)

    assert (rejected / "img0.png").read_bytes() == b"old"
    assert (rejected / "img0 (1).png").read_bytes() == b"older"
    assert (rejected / "img0 (2).png").read_bytes() == b"x"


def test_move_kept_to_kept_folder(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.APPROVE, Mark.DELETE, None])
    trash = FakeTrash()
    result = run_commit(
        plan_commit(lib, move_kept=True), Destination.RECYCLE_BIN, trash=trash
    )

    assert (tmp_path / KEPT_DIR / "img0.png").exists()
    assert not (tmp_path / "img0.png").exists()
    assert (tmp_path / "img2.png").exists()
    assert set(result.done) == {tmp_path / "img0.png", tmp_path / "img1.png"}


def test_one_failure_does_not_stop_the_rest(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.DELETE, Mark.DELETE, Mark.DELETE])
    trash = FakeTrash(fail={"img1.png"})
    result = run_commit(plan_commit(lib), Destination.RECYCLE_BIN, trash=trash)

    assert result.done == [tmp_path / "img0.png", tmp_path / "img2.png"]
    assert [path for path, _ in result.failed] == [tmp_path / "img1.png"]
    assert "access denied" in result.failed[0][1]


def test_empty_plan_touches_nothing(tmp_path: Path) -> None:
    lib = make_marked_library(tmp_path, [Mark.APPROVE, None])
    result = run_commit(plan_commit(lib), Destination.REJECTED_FOLDER)

    assert result.done == [] and result.failed == []
    assert not (tmp_path / REJECTED_DIR).exists()
    assert not (tmp_path / KEPT_DIR).exists()


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1536, "1.5 KB"),
        (5 * 1024**2, "5.0 MB"),
        (int(1.25 * 1024**3), "1.2 GB"),
        (3 * 1024**4, "3.0 TB"),
    ],
)
def test_format_bytes(size: int, text: str) -> None:
    assert format_bytes(size) == text


def test_moves_keep_the_subfolder_structure(tmp_path: Path) -> None:
    for rel in ["a/same.png", "b/same.png"]:
        (tmp_path / rel).parent.mkdir()
        (tmp_path / rel).write_bytes(rel.encode())
    lib = Library.from_folder(tmp_path)
    lib.marks = {lib.paths[0]: Mark.DELETE, lib.paths[1]: Mark.APPROVE}

    run_commit(plan_commit(lib, move_kept=True), Destination.REJECTED_FOLDER)

    assert (tmp_path / REJECTED_DIR / "a" / "same.png").read_bytes() == b"a/same.png"
    assert (tmp_path / KEPT_DIR / "b" / "same.png").read_bytes() == b"b/same.png"
    assert scan_folder(tmp_path) == []  # committed files don't come back
