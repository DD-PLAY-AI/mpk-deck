from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

DIAMETER = 12
CONNECTED_COLOR = "#3ddc84"
DISCONNECTED_COLOR = "#e0473c"


class MidiStatusDot(QWidget):
    """Small colored dot showing MIDI connection state. Click to retry when disconnected."""

    retry_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(DIAMETER, DIAMETER)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("MIDI connecting...")
        self.set_connected(False)

    def set_connected(self, connected: bool) -> None:
        color = CONNECTED_COLOR if connected else DISCONNECTED_COLOR
        self.setStyleSheet(f"MidiStatusDot {{ background: {color}; border-radius: {DIAMETER // 2}px; }}")
        self.setToolTip("MIDI connected" if connected else "MIDI disconnected — click to retry")

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.retry_requested.emit()
        super().mousePressEvent(event)
