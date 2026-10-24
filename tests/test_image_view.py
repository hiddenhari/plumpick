import pytest
from PySide6.QtCore import QPointF, QSizeF

from plumpick.cull import image_view
from plumpick.cull.image_view import (
    MAX_ZOOM,
    MIN_ZOOM,
    centered_offset,
    clamp_offset,
    clamp_scale,
    fit_scale,
    wheel_factor,
    zoom_at,
)


def image_point_under(anchor: QPointF, scale: float, offset: QPointF) -> QPointF:
    """Which image pixel is drawn at the given widget position."""
    return (anchor - offset) / scale


# --- fit_scale ---------------------------------------------------------------


def test_fit_scale_wide_image_limited_by_width():
    assert fit_scale(QSizeF(2000, 1000), QSizeF(1000, 1000)) == pytest.approx(0.5)


def test_fit_scale_tall_image_limited_by_height():
    assert fit_scale(QSizeF(1000, 2000), QSizeF(1000, 1000)) == pytest.approx(0.5)


def test_fit_scale_upscales_small_image():
    assert fit_scale(QSizeF(100, 100), QSizeF(400, 800)) == pytest.approx(4.0)


def test_fit_scale_zero_sizes_do_not_crash():
    assert fit_scale(QSizeF(0, 0), QSizeF(800, 600)) == 1.0
    assert fit_scale(QSizeF(800, 600), QSizeF(0, 0)) == 1.0


# --- clamp_scale -------------------------------------------------------------


def test_clamp_scale_limits_are_relative_to_fit():
    assert clamp_scale(1000.0, 0.5) == pytest.approx(MAX_ZOOM * 0.5)
    assert clamp_scale(0.0001, 0.5) == pytest.approx(MIN_ZOOM * 0.5)
    assert clamp_scale(1.0, 0.5) == 1.0


def test_clamp_scale_always_allows_actual_size():
    # an 8000px image in an 800px view has fit 0.1, so 8x fit would stop short of 100%
    assert clamp_scale(1.0, 0.1) == 1.0


# --- wheel_factor ------------------------------------------------------------


def test_wheel_zero_delta_is_identity():
    assert wheel_factor(0) == 1.0


def test_wheel_direction():
    assert wheel_factor(120) > 1 > wheel_factor(-120)


def test_wheel_zoom_in_then_out_cancels():
    assert wheel_factor(120) * wheel_factor(-120) == pytest.approx(1.0)


def test_wheel_one_notch_is_zoom_step():
    assert wheel_factor(120) == pytest.approx(image_view.ZOOM_STEP)


def test_wheel_small_trackpad_delta_is_a_fraction_of_a_step():
    assert 1.0 < wheel_factor(15) < wheel_factor(120)


# --- zoom_at -----------------------------------------------------------------


def test_zoom_at_hand_calculated_case():
    scale, offset = zoom_at(1.0, QPointF(0, 0), QPointF(100, 100), 2.0, fit=1.0)
    assert scale == pytest.approx(2.0)
    assert offset == QPointF(-100, -100)


def test_zoom_at_keeps_point_under_cursor():
    scale, offset = 0.7, QPointF(-40, 25)
    anchor = QPointF(310, 190)
    before = image_point_under(anchor, scale, offset)

    new_scale, new_offset = zoom_at(scale, offset, anchor, 1.6, fit=0.5)

    after = image_point_under(anchor, new_scale, new_offset)
    assert after.x() == pytest.approx(before.x())
    assert after.y() == pytest.approx(before.y())


@pytest.mark.parametrize("factor", [1000.0, 0.0001])
def test_zoom_at_clamps_scale_but_keeps_point_under_cursor(factor):
    fit = 0.5
    scale, offset = 1.0, QPointF(-120, -60)
    anchor = QPointF(250, 140)
    before = image_point_under(anchor, scale, offset)

    new_scale, new_offset = zoom_at(scale, offset, anchor, factor, fit)

    assert MIN_ZOOM * fit <= new_scale <= MAX_ZOOM * fit
    after = image_point_under(anchor, new_scale, new_offset)
    assert after.x() == pytest.approx(before.x())
    assert after.y() == pytest.approx(before.y())


# --- centered_offset / clamp_offset --------------------------------------------


def test_centered_offset():
    assert centered_offset(QSizeF(100, 50), 2.0, QSizeF(400, 300)) == QPointF(100, 100)


def test_clamp_offset_centers_image_smaller_than_view():
    image, view = QSizeF(100, 100), QSizeF(400, 300)
    result = clamp_offset(QPointF(-999, 999), image, 1.0, view)
    assert result == centered_offset(image, 1.0, view)


def test_clamp_offset_big_image_cannot_leave_a_gap():
    image, view = QSizeF(1000, 800), QSizeF(400, 300)  # scaled size 1000x800
    # dragged too far right/down: gap on the left/top
    assert clamp_offset(QPointF(500, 500), image, 1.0, view) == QPointF(0, 0)
    # dragged too far left/up: gap on the right/bottom
    assert clamp_offset(QPointF(-9999, -9999), image, 1.0, view) == QPointF(-600, -500)
    # inside the allowed range: unchanged
    assert clamp_offset(QPointF(-100, -200), image, 1.0, view) == QPointF(-100, -200)


def test_clamp_offset_axes_are_independent():
    image, view = QSizeF(1000, 100), QSizeF(400, 300)  # wide enough to pan, short enough to center
    result = clamp_offset(QPointF(-100, 999), image, 1.0, view)
    assert result == QPointF(-100, 100)
