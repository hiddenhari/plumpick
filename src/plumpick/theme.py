"""Colors that follow the system light/dark setting."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Theme:
    background: str  # window and area behind the picture
    status_bar: str
    text: str
    text_strong: str
    text_dim: str
    key_border: str
    accent: str
    accent_pressed: str


DARK = Theme("#3a3a3a", "#484848", "#d0d0d0", "#f2f2f2", "#b0b0b0", "#808080", "#2f81f7", "#1f5fbf")
LIGHT = Theme("#dcdcdc", "#eeeeee", "#333333", "#111111", "#555555", "#999999", "#0969da", "#074a9e")


def current() -> Theme:
    scheme = QGuiApplication.styleHints().colorScheme()
    return LIGHT if scheme == Qt.ColorScheme.Light else DARK


def on_change(callback) -> None:
    """Call `callback` whenever the system switches between light and dark."""
    QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _scheme: callback())
