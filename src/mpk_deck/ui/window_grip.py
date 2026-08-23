from PySide6.QtCore import Qt

from mpk_deck.ui.hit_test import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTCAPTION,
    HTCLIENT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
    classify_hit,
)
from mpk_deck.ui.resize_geometry import compute_resized_rect

BORDER = 6

_CURSOR_FOR_ZONE = {
    HTLEFT: Qt.CursorShape.SizeHorCursor,
    HTRIGHT: Qt.CursorShape.SizeHorCursor,
    HTTOP: Qt.CursorShape.SizeVerCursor,
    HTBOTTOM: Qt.CursorShape.SizeVerCursor,
    HTTOPLEFT: Qt.CursorShape.SizeFDiagCursor,
    HTBOTTOMRIGHT: Qt.CursorShape.SizeFDiagCursor,
    HTTOPRIGHT: Qt.CursorShape.SizeBDiagCursor,
    HTBOTTOMLEFT: Qt.CursorShape.SizeBDiagCursor,
    HTCAPTION: Qt.CursorShape.SizeAllCursor,
}


class WindowGripMixin:
    """Mix into a QWidget so its own (unoccupied) area moves or aspect-lock-resizes the
    top-level window, based on where the pointer lands relative to `BORDER` px of edge.

    Must live on the widget that actually receives the click (child widgets like buttons
    don't propagate mouse events to their parent), same reasoning as the old DraggableMixin.
    """

    def __init__(self, *args, aspect: float, min_width: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.locked_aspect = aspect
        self._min_width = min_width
        self._active_zone: int | None = None
        self._press_global = None
        self._press_geometry = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._classify(event.position().toPoint())
            if zone != HTCLIENT:
                self._active_zone = zone
                self._press_global = event.globalPosition().toPoint()
                self._press_geometry = self.window().geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._active_zone is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._apply_drag(event)
        else:
            self._update_hover_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._active_zone = None
        self._press_global = None
        self._press_geometry = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._active_zone is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def _classify(self, pos) -> int:
        over_interactive = self.childAt(pos) is not None
        return classify_hit(pos.x(), pos.y(), self.width(), self.height(), BORDER, over_interactive=over_interactive)

    def _update_hover_cursor(self, pos) -> None:
        cursor = _CURSOR_FOR_ZONE.get(self._classify(pos))
        if cursor is None:
            self.unsetCursor()
        else:
            self.setCursor(cursor)

    def _apply_drag(self, event) -> None:
        global_pos = event.globalPosition().toPoint()
        dx = global_pos.x() - self._press_global.x()
        dy = global_pos.y() - self._press_global.y()
        rect = self._press_geometry
        if self._active_zone == HTCAPTION:
            self.window().move(rect.x() + dx, rect.y() + dy)
            return
        x, y, w, h = compute_resized_rect(
            self._active_zone,
            x=rect.x(),
            y=rect.y(),
            w=rect.width(),
            h=rect.height(),
            dx=dx,
            dy=dy,
            aspect=self.locked_aspect,
            min_w=self._min_width,
        )
        self.window().setGeometry(x, y, w, h)
