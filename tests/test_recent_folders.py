from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from plumpick.app.recent_folders import (
    MAX_RECENT_FOLDERS,
    load_recent_folders,
    remember_folder,
    update_recent_folders,
)


def test_update_recent_folders_moves_selected_to_front_and_deduplicates(
    tmp_path: Path,
) -> None:
    folders = [str(tmp_path / "one"), str(tmp_path / "two")]
    result = update_recent_folders(folders, folders[1])
    assert result == [str(Path(folders[1]).resolve()), str(Path(folders[0]).resolve())]


def test_update_recent_folders_respects_limit(tmp_path: Path) -> None:
    folders = [tmp_path / f"folder-{i}" for i in range(MAX_RECENT_FOLDERS + 2)]
    selected = tmp_path / "new-folder"
    result = update_recent_folders([str(path) for path in folders], selected)
    assert len(result) == MAX_RECENT_FOLDERS
    assert result[0] == str(selected.resolve())
    assert str(folders[-1].resolve()) not in result


def test_remember_and_load_recent_folders_persist_and_skip_missing(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    remember_folder(first, settings)
    remember_folder(second, settings)
    settings.sync()

    assert load_recent_folders(settings) == [str(second.resolve()), str(first.resolve())]
    settings.setValue("recentFolders", [str(first), str(tmp_path / "missing")])
    assert load_recent_folders(settings) == [str(first.resolve())]
