"""Render image with zooming and panning"""

from PySide6.QtCore import QPoint, QPointF, QSizeF, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QMenu, QWidget

ZOOM_STEP = 1.15  # zoom change per wheel notch
NOTCH = 120  # Qt reports one standard wheel notch as angleDelta().y() == 120
MIN_ZOOM = 0.1  # limits, as multiples of the fit scale
MAX_ZOOM = 8.0
EDGE_WIDTH = 64  # viewport edge area reserved for previous/next clicks
EDGE_GRADIENT_EXTRA = 20  # softens the transition just inside the click zone


class ImageView(QWidget):
    zoomChanged = Signal(float)  # emitted with the new scale whenever it changes
    navigate_previous = Signal()
    navigate_next = Signal()
    edge_hover_changed = Signal(str)
    keep_requested = Signal()
    reject_requested = Signal()
    clear_mark_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = QPixmap()  # full-size image; drawn scaled by the painter
        self._message = ""  # shown centered when there is no image
        self._text_color = QColor("#ccc")
        self._fit_mode = True  # True: refit on resize; False: user has zoomed/panned
        self._drag_last: QPointF | None = None  # last mouse position while dragging
        self.scale = 1.0  # pixels per image pixel
        self.offset = QPointF(0, 0)  # top-left corner of image, widget coords
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep Space for navigation
        self.setMouseTracking(True)
        self._hover_x: float | None = None
        self._has_mark = False

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Show a new image, fitted to the view."""
        self._pixmap = pixmap
        self._message = ""
        self.fit()

    def set_message(self, text: str) -> None:
        """Show text instead of an image (empty folder, failed decode)."""
        self._pixmap = QPixmap()
        self._message = text
        self.update()

    def set_has_mark(self, marked: bool) -> None:
        self._has_mark = marked

    def fit(self) -> None:
        """Scale the whole image to fit the view, centered."""
        self._fit_mode = True
        self.scale = fit_scale(self._image_size(), self._view_size())
        self.offset = centered_offset(self._image_size(), self.scale, self._view_size())
        self._view_changed()

    def set_actual_size(self, anchor: QPointF | None = None) -> None:
        """Zoom to 100% (one image pixel per screen pixel) about anchor, default the center."""
        if self._pixmap.isNull():
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        fit = fit_scale(self._image_size(), self._view_size())
        self.scale, offset = zoom_at(self.scale, self.offset, anchor, 1.0 / self.scale, fit)
        self.offset = clamp_offset(offset, self._image_size(), self.scale, self._view_size())
        self._fit_mode = False
        self._view_changed()

    def toggle_zoom(self, anchor: QPointF | None = None) -> None:
        """Fit -> 100%; anything else (100%, wheel-zoomed, panned) -> fit."""
        if self._fit_mode:
            self.set_actual_size(anchor)
        else:
            self.fit()

    @property
    def zoom_percent(self) -> int | None:
        """Current zoom as a percentage of the image's pixels, or None without an image."""
        return None if self._pixmap.isNull() else round(self.scale * 100)

    def set_text_color(self, color: str) -> None:
        self._text_color = QColor(color)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self._pixmap.isNull():
            painter.setPen(self._text_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.restore()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        keep = menu.addAction("Keep Image")
        reject = menu.addAction("Reject Image")
        clear = menu.addAction("Clear mark")
        clear.setEnabled(self._has_mark)
        chosen = self._exec_context_menu(menu, event.globalPos())
        if chosen is keep:
            self.keep_requested.emit()
        elif chosen is reject:
            self.reject_requested.emit()
        elif chosen is clear:
            self.clear_mark_requested.emit()

    def _exec_context_menu(self, menu: QMenu, position: QPoint) -> QAction | None:
        """Execute the menu; kept separate so actions can be tested without a modal UI."""
        return menu.exec(position)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap.isNull():
            event.ignore()
            return
        fit = fit_scale(self._image_size(), self._view_size())
        factor = wheel_factor(event.angleDelta().y())
        self.scale, offset = zoom_at(self.scale, self.offset, event.position(), factor, fit)
        self.offset = clamp_offset(offset, self._image_size(), self.scale, self._view_size())
        self._fit_mode = False
        self._view_changed()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._pixmap.isNull():
            x = event.position().x()
            if x < EDGE_WIDTH:
                self.navigate_previous.emit()
                event.accept()
                return
            if x >= self.width() - EDGE_WIDTH:
                self.navigate_next.emit()
                event.accept()
                return
            self.toggle_zoom(event.position())
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            if x < EDGE_WIDTH:
                self.navigate_previous.emit()
                event.accept()
                return
            if x >= self.width() - EDGE_WIDTH:
                self.navigate_next.emit()
                event.accept()
                return
        if event.button() == Qt.MouseButton.LeftButton and not self._pixmap.isNull():
            self._drag_last = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = event.position().x()
        hover = x if x < EDGE_WIDTH or x >= self.width() - EDGE_WIDTH else None
        if hover != self._hover_x:
            self._hover_x = hover
            self.edge_hover_changed.emit(
                "left" if hover is not None and hover < EDGE_WIDTH
                else "right" if hover is not None
                else ""
            )
            self.update()
        if self._drag_last is None:
            super().mouseMoveEvent(event)
            return
        delta = event.position() - self._drag_last
        self._drag_last = event.position()
        offset = clamp_offset(
            self.offset + delta, self._image_size(), self.scale, self._view_size()
        )
        if offset != self.offset:  # a fitted image can't move, so it stays in fit mode
            self.offset = offset
            self._fit_mode = False
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_last is not None:
            self._drag_last = None
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit()
        else:
            self.offset = clamp_offset(
                self.offset, self._image_size(), self.scale, self._view_size()
            )

    def leaveEvent(self, event) -> None:
        self._hover_x = None
        self.edge_hover_changed.emit("")
        self.update()
        super().leaveEvent(event)

    def _view_changed(self) -> None:
        self.update()
        self.zoomChanged.emit(self.scale)

    def _image_size(self) -> QSizeF:
        return QSizeF(self._pixmap.size())

    def _view_size(self) -> QSizeF:
        return QSizeF(self.size())


def fit_scale(image_size: QSizeF, view_size: QSizeF) -> float:
    """Scale at which the whole image just fits inside the view."""
    if min(image_size.width(), image_size.height(), view_size.width(), view_size.height()) <= 0:
        return 1.0
    return min(
        view_size.width() / image_size.width(),
        view_size.height() / image_size.height(),
    )


def clamp_scale(scale: float, fit: float) -> float:
    """Keep scale within [MIN_ZOOM, MAX_ZOOM] times the fit scale.

    The upper limit never drops below 100%, so a huge image can still be viewed at 1:1.
    """
    return max(MIN_ZOOM * fit, min(max(MAX_ZOOM * fit, 1.0), scale))


def wheel_factor(angle_delta_y: float) -> float:
    """Number to multiply scale by for a wheel delta; exponential so in/out cancel."""
    return ZOOM_STEP ** (angle_delta_y / NOTCH)


def zoom_at(
    scale: float, offset: QPointF, anchor: QPointF, factor: float, fit: float
) -> tuple[float, QPointF]:
    """Zoom by factor while the image point under anchor stays under anchor."""
    new_scale = clamp_scale(scale * factor, fit)
    ratio = new_scale / scale
    new_offset = anchor - (anchor - offset) * ratio
    return new_scale, new_offset


def centered_offset(image_size: QSizeF, scale: float, view_size: QSizeF) -> QPointF:
    """Offset that centers the scaled image in the view."""
    return QPointF(
        (view_size.width() - image_size.width() * scale) / 2,
        (view_size.height() - image_size.height() * scale) / 2,
    )


def _clamp_axis(offset: float, scaled: float, view: float) -> float:
    if scaled <= view:
        return (view - scaled) / 2  # smaller than the view: stay centered
    return max(view - scaled, min(0.0, offset))  # bigger: no gap at either edge


def clamp_offset(
    offset: QPointF, image_size: QSizeF, scale: float, view_size: QSizeF
) -> QPointF:
    """Center the image on axes where it fits; otherwise keep it covering the view."""
    return QPointF(
        _clamp_axis(offset.x(), image_size.width() * scale, view_size.width()),
        _clamp_axis(offset.y(), image_size.height() * scale, view_size.height()),
    )
