"""Persistent, de-duplicated list of recently opened image folders."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

SETTINGS_ORG = "plumpick"
SETTINGS_APP = "plumpick"
RECENT_FOLDERS_KEY = "recentFolders"
MAX_RECENT_FOLDERS = 10


def normalize_folder(path: Path | str) -> str:
    """Return a stable absolute path for display and duplicate detection."""
    return str(Path(path).expanduser().resolve())


def update_recent_folders(
    folders: list[str], path: Path | str, limit: int = MAX_RECENT_FOLDERS
) -> list[str]:
    """Move `path` to the front and return at most `limit` unique folders."""
    selected = normalize_folder(path)
    key = selected.casefold()
    result = [selected]
    seen = {key}
    for folder in folders:
        normalized = normalize_folder(folder)
        folded = normalized.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(normalized)
        if len(result) >= limit:
            break
    return result[:limit]


def load_recent_folders(settings: QSettings | None = None) -> list[str]:
    settings = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
    stored = settings.value(RECENT_FOLDERS_KEY, [], type=list)
    return [folder for folder in stored if Path(folder).is_dir()]


def remember_folder(path: Path | str, settings: QSettings | None = None) -> list[str]:
    settings = settings or QSettings(SETTINGS_ORG, SETTINGS_APP)
    folders = update_recent_folders(load_recent_folders(settings), path)
    settings.setValue(RECENT_FOLDERS_KEY, folders)
    return folders
