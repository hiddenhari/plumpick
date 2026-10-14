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
