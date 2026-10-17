import os
from pathlib import Path

import pytest

from plumpick.library import Library, Mark, scan_folder


def make_library(tmp_path: Path, n: int = 3) -> Library:
    """Path.cwd() might differ from actual pytest directory
    use make_library_with_files if path matters"""
    return Library(tmp_path, [tmp_path / f"img{i}.png" for i in range(n)])


def make_library_with_files(root: Path, n: int = 3) -> Library:
    for i in range(n):
        (root / f"img{i}.png").touch()  # make_library(tmp_path) makes no real file
    return Library.from_folder(root)


def test_scan_folder_keeps_only_images_sorted(tmp_path: Path) -> None:
    for name in ["b.PNG", "a.jpg", "notes.txt", "c.webp"]:
        (tmp_path / name).touch()
    (tmp_path / "sub.png").mkdir()  # a folder with an image-like name

    assert [p.name for p in scan_folder(tmp_path)] == ["a.jpg", "b.PNG", "c.webp"]


def test_navigation_stops_at_both_ends(tmp_path: Path) -> None:
    lib = make_library(tmp_path, 2)
    assert not lib.prev()
    assert lib.next()
    assert lib.current == tmp_path / "img1.png"
    assert not lib.next()
    assert lib.index == 1


def test_marks_follow_the_image_not_the_cursor(tmp_path: Path) -> None:
    lib = make_library(tmp_path, 3)
    lib.set_mark(Mark.APPROVE)
    lib.next()
    lib.set_mark(Mark.DELETE)
    lib.prev()

    assert lib.current_mark is Mark.APPROVE
    assert lib.count(Mark.APPROVE) == 1
    assert lib.count(Mark.DELETE) == 1
    assert lib.undecided == 1


def test_clearing_and_overwriting_marks(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.next()
    lib.set_mark(Mark.APPROVE)
    lib.set_mark(Mark.DELETE)
    assert lib.current_mark is Mark.DELETE
    lib.set_mark(None)
    assert lib.current_mark is None
    assert lib.undecided == 3


def test_empty_library_is_safe(tmp_path: Path) -> None:
    lib = make_library(tmp_path, 0)
    assert lib.current is None
    assert lib.current_mark is None
    lib.set_mark(Mark.DELETE)  # no-op, must not raise
    assert not lib.next()


def test_goto(tmp_path: Path) -> None:
    IMAGE_COUNT = 10
    lib = make_library(tmp_path, IMAGE_COUNT)

    assert lib.goto(IMAGE_COUNT) is False
    assert lib.current == tmp_path / "img0.png"
    lib.goto(IMAGE_COUNT - 1)
    assert lib.current == tmp_path / f"img{IMAGE_COUNT - 1}.png"
    assert lib.goto(-1) is False
    assert lib.current == tmp_path / f"img{IMAGE_COUNT - 1}.png"
    lib.goto(0)
    assert lib.current == tmp_path / "img0.png"


def test_undo_basics(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    assert lib.undo() is False
    assert lib.redo() is False

    lib.set_mark(Mark.APPROVE)
    assert lib.undo() is True
    assert lib.current_mark is None
    assert lib.redo() is True
    assert lib.current_mark == Mark.APPROVE


def test_undo_dont_record_navigation(tmp_path: Path) -> None:
    # redos come from undos, so can't record navigations if undo didn't
    lib = make_library(tmp_path)
    lib.next()
    assert lib.undo() is False
    assert lib.current == tmp_path / "img1.png"


def test_undo_jump_to_image(tmp_path: Path) -> None:
    # undo/redo when on a different image jumps to the undoing image
    lib = make_library(tmp_path)
    lib.set_mark(Mark.APPROVE)
    edited_image = lib.current
    lib.next()
    lib.next()  # on img 2
    assert lib.undo() is True  # on img 0
    assert lib.current == edited_image
    assert lib.current_mark is None
    assert lib.index == 0
    lib.next()  # on img 1
    assert lib.redo() is True  # on img 0
    assert lib.current == edited_image
    assert lib.current_mark is Mark.APPROVE
    assert lib.index == 0


def test_undo_image_no_index(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.set_mark(Mark.DELETE)
    lib.next()
    lib.paths.remove(tmp_path / "img0.png")
    index, current = lib.index, lib.current

    assert lib.undo() is True
    assert lib.index == index  # viewer/cursor didn't move
    assert lib.current == current
    assert tmp_path / "img0.png" not in lib.marks

    assert lib.redo() is True
    assert lib.index == index
    assert lib.current == current
    assert tmp_path / "img0.png" in lib.marks


def test_clear_then_undo(tmp_path: Path) -> None:
    lib = make_library(tmp_path, 1)
    lib.set_mark(Mark.APPROVE)
    assert lib.current_mark is Mark.APPROVE and lib.undecided == 0
    lib.undo()
    assert lib.current_mark is None and lib.undecided == 1


def test_redo_is_cleared_after_editing(tmp_path: Path) -> None:
    # redo is cleared when editing
    lib = make_library(tmp_path)
    lib.set_mark(Mark.APPROVE)
    assert lib.undo() is True
    lib.set_mark(Mark.DELETE)
    assert lib.redo() is False
    assert lib.current_mark == Mark.DELETE


def test_undo_only_after_real_edit(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.set_mark(None)
    assert lib.undo() is False

    lib.next()
    lib.set_mark(Mark.APPROVE)
    lib.set_mark(Mark.APPROVE)  # only one effective edit
    assert lib.undo() is True
    assert lib.undo() is False


def test_undo_sequence(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.set_mark(None)
    lib.set_mark(Mark.APPROVE)
    lib.set_mark(Mark.DELETE)
    lib.set_mark(None)
    assert lib.undo() is True and lib.current_mark is Mark.DELETE
    assert lib.undo() is True and lib.current_mark is Mark.APPROVE
    assert lib.undo() is True and lib.current_mark is None
    assert lib.undo() is False
    assert lib.redo() is True and lib.current_mark is Mark.APPROVE
    assert lib.redo() is True and lib.current_mark is Mark.DELETE
    assert lib.redo() is True and lib.current_mark is None
    assert lib.redo() is False


def test_undo_undecided_count(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.set_mark(Mark.APPROVE)
    lib.next()
    lib.set_mark(Mark.APPROVE)
    lib.next()
    lib.set_mark(Mark.DELETE)
    assert lib.undecided == 0
    assert lib.undo() is True and lib.undecided == 1
    assert lib.undo() is True and lib.undecided == 2
    assert lib.undo() is True and lib.undecided == 3
    assert lib.undo() is False and lib.undecided == 3
    assert lib.redo() is True and lib.undecided == 2
    assert lib.redo() is True and lib.undecided == 1
    assert lib.redo() is True and lib.undecided == 0
    assert lib.redo() is False and lib.undecided == 0


def test_save_load_library(tmp_path: Path):
    """test reloading library recovers index (last viewing image), marks"""
    test_count = 10
    lib = make_library_with_files(tmp_path, test_count)
    for i in range(test_count):
        lib.marks[tmp_path / f"img{i}.png"] = Mark.APPROVE

    lib.index = 4
    lib.save_session()
    lib = Library.from_folder(tmp_path)  # restores the saved session
    assert lib.index == 4
    assert len(lib.paths) == test_count
    assert len(lib.marks) == test_count
    for i in range(test_count):
        assert lib.marks[tmp_path / f"img{i}.png"] == Mark.APPROVE


def test_load_missing_files(tmp_path: Path):
    """test missing files are dropped when reloading"""
    test_count = 10
    lib = make_library_with_files(tmp_path, test_count)
    for i in range(test_count):
        lib.marks[tmp_path / f"img{i}.png"] = Mark.DELETE
    assert len(lib.marks) == test_count

    lib.index = test_count - 1
    lib.save_session()

    deleted = range(0, test_count, 2)
    for i in deleted:
        (tmp_path / f"img{i}.png").unlink()
    remaining = test_count - len(deleted)

    lib = Library.from_folder(tmp_path)
    assert len(lib.paths) == remaining
    assert len(lib.marks) == remaining
    assert lib.index == remaining - 1  # clamped, not past the end


def test_session_survives_moving_folder(tmp_path: Path) -> None:
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    lib = make_library_with_files(old, 3)
    lib.next()
    lib.set_mark(Mark.DELETE)
    old.rename(new)

    moved = Library.from_folder(new)
    assert moved.marks == {new / "img1.png": Mark.DELETE}
    assert moved.index == 1


def test_undo_is_saved(tmp_path: Path) -> None:
    lib = make_library_with_files(tmp_path, 2)
    lib.set_mark(Mark.APPROVE)
    lib.undo()
    assert Library.from_folder(tmp_path).marks == {}


def test_corrupt_session_is_ignored(tmp_path: Path) -> None:
    (tmp_path / ".plumpick.json").write_text('{"index": "x"}', encoding="utf-8")
    lib = make_library_with_files(tmp_path, 2)
    assert lib.index == 0 and lib.marks == {}


def test_failed_save_keeps_old_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = make_library_with_files(tmp_path, 2)
    lib.set_mark(Mark.APPROVE)
    save = tmp_path / ".plumpick.json"

    lib.next()
    lib.set_mark(Mark.DELETE)  # set_mark autosaves
    before = save.read_text()
    lib.marks.clear()  # unsaved change

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        lib.save_session()

    assert save.read_text() == before
    assert not list(tmp_path.glob("*.tmp"))  # temp file cleaned up
    assert not list(tmp_path.parent.glob("*.tmp"))  # and nothing leaked outside

