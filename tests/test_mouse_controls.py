"""Mouse behavior for the image viewport and its frame-wide edge overlay."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from plumpick.cull import cull_window
from plumpick.cull.cull_window import CullWindow, _EdgeGradient
from plumpick.cull.image_view import EDGE_WIDTH, ImageView
from plumpick.cull.library import Library, Mark


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Create one headless Qt application for widget interaction tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def mouse_event(
    event_type: QEvent.Type,
    x: float,
    y: float,
    *,
    button: Qt.MouseButton = Qt.MouseButton.NoButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        QPointF(x, y),
        QPointF(x, y),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_edge_hover_signal_tracks_left_right_and_leave(qapp: QApplication) -> None:
    view = ImageView()
    view.resize(320, 240)
    edges: list[str] = []
    view.edge_hover_changed.connect(edges.append)

    view.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, EDGE_WIDTH / 2, 100))
    view.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, 319, 100))
    view.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, 160, 100))

    assert edges == ["left", "right", ""]

    view.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, 1, 100))
    view.leaveEvent(QEvent(QEvent.Type.Leave))
    assert edges[-1] == ""


def test_clicking_view_edges_requests_navigation(qapp: QApplication) -> None:
    view = ImageView()
    view.resize(320, 240)
    navigation: list[str] = []
    view.navigate_previous.connect(lambda: navigation.append("previous"))
    view.navigate_next.connect(lambda: navigation.append("next"))

    view.mousePressEvent(
        mouse_event(
            QEvent.Type.MouseButtonPress,
            EDGE_WIDTH / 2,
            100,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        )
    )
    view.mousePressEvent(
        mouse_event(
            QEvent.Type.MouseButtonPress,
            320 - EDGE_WIDTH / 2,
            100,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        )
    )
    view.mousePressEvent(
        mouse_event(
            QEvent.Type.MouseButtonPress,
            160,
            100,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        )
    )

    assert navigation == ["previous", "next"]


@pytest.mark.parametrize("edge_x", [0, 319])
def test_double_click_in_navigation_zone_does_not_toggle_zoom(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, edge_x: int
) -> None:
    view = ImageView()
    view.resize(320, 240)
    view.set_pixmap(QPixmap(10, 10))
    zoom_anchors: list[QPointF] = []
    navigation: list[str] = []
    view.navigate_previous.connect(lambda: navigation.append("previous"))
    view.navigate_next.connect(lambda: navigation.append("next"))
    monkeypatch.setattr(view, "toggle_zoom", zoom_anchors.append)

    view.mouseDoubleClickEvent(
        mouse_event(
            QEvent.Type.MouseButtonDblClick,
            edge_x,
            100,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        )
    )
    view.mouseDoubleClickEvent(
        mouse_event(
            QEvent.Type.MouseButtonDblClick,
            160,
            100,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        )
    )

    assert zoom_anchors == [QPointF(160, 100)]
    assert navigation == ["previous" if edge_x < EDGE_WIDTH else "next"]


@pytest.mark.parametrize(
    ("action_index", "signal_name"),
    [
        (0, "keep_requested"),
        (1, "reject_requested"),
        (2, "clear_mark_requested"),
    ],
)
def test_context_menu_emits_selected_mark_action(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    action_index: int,
    signal_name: str,
) -> None:
    view = ImageView()
    view.set_has_mark(True)
    emitted: list[str] = []
    getattr(view, signal_name).connect(lambda: emitted.append(signal_name))

    def choose_action(menu: QMenu, _position: QPoint) -> object:
        return menu.actions()[action_index]

    monkeypatch.setattr(view, "_exec_context_menu", choose_action)
    view.contextMenuEvent(SimpleNamespace(globalPos=lambda: QPoint(10, 10)))

    assert emitted == [signal_name]


def test_context_menu_disables_clear_when_unmarked(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = ImageView()
    enabled_states: list[bool] = []

    def inspect_menu(menu: QMenu, _position: QPoint) -> None:
        enabled_states.extend(action.isEnabled() for action in menu.actions())
        return None

    monkeypatch.setattr(view, "_exec_context_menu", inspect_menu)
    view.contextMenuEvent(SimpleNamespace(globalPos=lambda: QPoint(10, 10)))

    assert enabled_states == [True, True, False]


def test_mark_menu_click_sets_mark_without_advancing(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = [tmp_path / "one.png", tmp_path / "two.png"]
    for path in paths:
        image = QImage(2, 2, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.white)
        assert image.save(str(path))

    monkeypatch.setattr(cull_window.theme, "on_change", lambda _callback: None)
    window = CullWindow(Library(tmp_path, paths))
    advance_calls: list[Mark] = []
    set_mark_calls: list[Mark] = []
    original_set_mark = window._set_mark

    def record_set_mark(mark: Mark) -> None:
        set_mark_calls.append(mark)
        original_set_mark(mark)

    monkeypatch.setattr(window, "_set_mark", record_set_mark)
    monkeypatch.setattr(window, "mark_and_advance", advance_calls.append)

    for action_index, expected_mark in ((0, Mark.APPROVE), (1, Mark.DELETE)):
        monkeypatch.setattr(
            window.image_view,
            "_exec_context_menu",
            lambda menu, _position, index=action_index: menu.actions()[index],
        )
        window.image_view.contextMenuEvent(
            SimpleNamespace(globalPos=lambda: QPoint(10, 10))
        )

        assert window.library.index == 0
        assert window.library.current_mark is expected_mark

    assert set_mark_calls == [Mark.APPROVE, Mark.DELETE]
    assert advance_calls == []
    window.close()


@pytest.mark.parametrize("edge, sample_x", [("left", 0), ("right", 299)])
def test_edge_gradient_reaches_outer_frame_edge(
    qapp: QApplication, edge: str, sample_x: int
) -> None:
    frame = QWidget()
    frame.resize(300, 200)
    view = ImageView(frame)
    view.setGeometry(6, 6, 288, 188)
    overlay = _EdgeGradient(frame, view)
    overlay.setGeometry(frame.rect())
    overlay.set_edge(edge)
    frame.show()
    qapp.processEvents()

    rendered = QImage(300, 200, QImage.Format.Format_ARGB32_Premultiplied)
    rendered.fill(Qt.GlobalColor.transparent)
    overlay.render(rendered)

    assert rendered.pixelColor(sample_x, 0).alpha() > 0

    frame.close()
