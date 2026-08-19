from PySide6.QtCore import Qt


class DraggableMixin:
    """Mix into a QWidget so clicking its own (unoccupied) background drags the top-level window.

    Qt mouse events don't bubble to the parent when a child ignores them, so this
    has to live on whichever widget actually receives the click (not the window).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_offset = None

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._drag_offset = None
        super().mouseReleaseEvent(event)
