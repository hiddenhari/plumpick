from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication, QMainWindow

from plumpick.app.app import _close_oldest_cull_window, _track_window
from plumpick.app.app_menu import (
    MAX_RECENT_FOLDERS,
    load_recent_folders,
    remember_folder,
    update_recent_folders,
)
from plumpick.cull import cull_window
from plumpick.cull.cull_window import CullWindow
from plumpick.cull.library import Library


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _process_deferred_deletes(qapp: QApplication) -> None:
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


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


def test_tracked_window_is_removed_when_closed(qapp: QApplication) -> None:
    windows: list[QMainWindow] = []
    window = QMainWindow()
    _track_window(windows, window)
    window.show()

    assert window.close()
    _process_deferred_deletes(qapp)

    assert windows == []


def test_opening_past_capacity_retires_oldest_cull_window(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cull_window.theme, "on_change", lambda _callback: None)
    windows: list[QMainWindow] = []
    cull_windows = [
        CullWindow(Library(tmp_path / str(index), [])) for index in range(8)
    ]
    for index in range(8):
        (tmp_path / str(index)).mkdir()
    for window in cull_windows:
        _track_window(windows, window)
        window.show()
    qapp.processEvents()

    assert _close_oldest_cull_window(windows)

    assert cull_windows[0].property("_plumpick_closing")
    assert not cull_windows[0].isVisible()
    assert all(window.isVisible() for window in cull_windows[1:])
    _process_deferred_deletes(qapp)
    assert cull_windows[0] not in windows
    assert len(windows) == 7
    for window in cull_windows[1:]:
        window.close()
    _process_deferred_deletes(qapp)


def test_closing_cull_window_saves_current_position(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cull_window.theme, "on_change", lambda _callback: None)
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    window = CullWindow(Library(tmp_path, [first, second]))
    window.library.next()

    assert window.close()
    _process_deferred_deletes(qapp)

    saved = json.loads((tmp_path / ".plumpick.json").read_text(encoding="utf-8"))
    assert saved["index"] == 1
