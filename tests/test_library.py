from pathlib import Path

from plumpick.library import Library, Mark, scan_folder


def make_library(n: int = 3) -> Library:
    return Library([Path(f"img{i}.png") for i in range(n)])


def test_scan_folder_keeps_only_images_sorted(tmp_path: Path) -> None:
    for name in ["b.PNG", "a.jpg", "notes.txt", "c.webp"]:
        (tmp_path / name).touch()
    (tmp_path / "sub.png").mkdir()  # a folder with an image-like name

    assert [p.name for p in scan_folder(tmp_path)] == ["a.jpg", "b.PNG", "c.webp"]


def test_navigation_stops_at_both_ends() -> None:
    lib = make_library(2)
    assert not lib.prev()
    assert lib.next()
    assert lib.current == Path("img1.png")
    assert not lib.next()
    assert lib.index == 1


def test_marks_follow_the_image_not_the_cursor() -> None:
    lib = make_library(3)
    lib.set_mark(Mark.APPROVE)
    lib.next()
    lib.set_mark(Mark.DELETE)
    lib.prev()

    assert lib.current_mark is Mark.APPROVE
    assert lib.count(Mark.APPROVE) == 1
    assert lib.count(Mark.DELETE) == 1
    assert lib.undecided == 1


def test_clearing_and_overwriting_marks() -> None:
    lib = make_library(1)
    lib.set_mark(Mark.APPROVE)
    lib.set_mark(Mark.DELETE)
    assert lib.current_mark is Mark.DELETE
    lib.set_mark(None)
    assert lib.current_mark is None
    assert lib.undecided == 1


def test_empty_library_is_safe() -> None:
    lib = make_library(0)
    assert lib.current is None
    assert lib.current_mark is None
    lib.set_mark(Mark.DELETE)  # no-op, must not raise
    assert not lib.next()


def test_goto() -> None:
    IMAGE_COUNT = 10
    lib = make_library(IMAGE_COUNT)

    assert lib.goto(IMAGE_COUNT) is False
    assert lib.current == Path("img0.png")
    lib.goto(IMAGE_COUNT - 1)
    assert lib.current == Path(f"img{IMAGE_COUNT - 1}.png")
    assert lib.goto(-1) is False
    assert lib.current == Path(f"img{IMAGE_COUNT - 1}.png")
    lib.goto(0)
    assert lib.current == Path("img0.png")


def test_undo() -> None:
    lib = make_library()
    assert lib.undo() is False
    assert lib.redo() is False

    # undo doesn't record navigation actions
    # redos come from undos, so can't record navigations if undo didn't
    lib.next()  # on img 1
    assert lib.undo() is False
    assert lib.current == Path("img1.png")

    # basic undo redo
    lib.set_mark(Mark.APPROVE)
    assert lib.undo() is True
    assert lib.current_mark is None
    assert lib.redo() is True
    assert lib.current_mark is Mark.APPROVE

    # undo/redo when on a different image jumps to the undoing image
    edited_image = lib.current # on img 1
    lib.next() # on img 2
    assert lib.undo() is True
    assert lib.current is edited_image # on img 1
    assert lib.current_mark is None
    lib.prev() # on img 0
    assert lib.redo() is True
    assert lib.current is edited_image # on img 1
    assert lib.current_mark is Mark.APPROVE

    # redo is cleared when editing after undo
    assert lib.undo() is True
    lib.set_mark(Mark.DELETE)
    assert lib.redo() is False
    assert lib.current_mark is Mark.DELETE


def test_undo_sequence():
    lib = make_library()

    # only effective edit has an undo
    lib.set_mark(None)
    assert lib.undo() is False

    # undo, redo sequence
    lib.set_mark(None)
    lib.set_mark(Mark.APPROVE)
    lib.set_mark(Mark.DELETE)
    lib.set_mark(None)
    assert lib.current_mark is None  # keep in case set_mark changed
    assert lib.undo() is True and lib.current_mark is Mark.DELETE
    assert lib.undo() is True and lib.current_mark is Mark.APPROVE
    assert lib.undo() is True and lib.current_mark is None
    assert lib.undo() is False
    assert lib.redo() is True and lib.current_mark is Mark.APPROVE
    assert lib.redo() is True and lib.current_mark is Mark.DELETE
    assert lib.redo() is True and lib.current_mark is None
    assert lib.redo() is False
    