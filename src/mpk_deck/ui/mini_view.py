from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX, ACCENT_RGB
from mpk_deck.core.action_registry import Binding
from mpk_deck.ui.action_config_dialog import ACTION_GLYPHS, ACTION_LABELS
from mpk_deck.ui.grid_layout import compute_pad_rects
from mpk_deck.ui.window_grip import WindowGripMixin

PAD_ORDER = ["pad_5", "pad_6", "pad_7", "pad_8", "pad_1", "pad_2", "pad_3", "pad_4"]

COLS, ROWS = 4, 2
ASPECT = COLS / ROWS
MARGIN, SPACING = 20, 8
BORDER_VISUAL = 2  # thin visible edge-light inside the wider (BORDER) grab zone

LIGHT_QSS = f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255,255,255,120), stop:1 rgba(235,240,255,150));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({ACCENT_RGB},130);
}}
QPushButton {{
    background: rgba(255,255,255,140);
    border: 1px solid rgba(120,120,140,90);
    border-radius: 12px;
    color: #23242b;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,190); }}
QPushButton:pressed {{ background: rgba(220,225,240,190); border: 1px solid {ACCENT_HEX}; }}
"""

DARK_QSS = f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20,22,28,217), stop:1 rgba(10,12,16,191));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({ACCENT_RGB},100);
}}
QPushButton {{
    background: rgba(255,255,255,18);
    border: 1px solid rgba(255,255,255,38);
    border-radius: 12px;
    color: #f2f4f8;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,34); }}
QPushButton:pressed {{ background: rgba(255,255,255,10); border: 1px solid {ACCENT_HEX}; }}
"""


class PadButton(QPushButton):
    """A button that tells single clicks (trigger) apart from double clicks (configure)."""

    activated = Signal()
    configure_requested = Signal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._click_timer.stop()
        self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)


class MiniView(WindowGripMixin, QWidget):
    pad_activated = Signal(str)
    pad_configure_requested = Signal(str)

    def __init__(self, labels: dict[str, str] | None = None, dark: bool = False, parent=None) -> None:
        super().__init__(parent, aspect=ASPECT, min_width=240)
        self.setObjectName("miniPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._labels = labels or {}
        self._pads: dict[str, PadButton] = {}
        for control in PAD_ORDER:
            button = PadButton(self._labels.get(control, control.upper()), self)
            button.activated.connect(lambda c=control: self.pad_activated.emit(c))
            button.configure_requested.connect(lambda c=control: self.pad_configure_requested.emit(c))
            self._pads[control] = button
        self.set_dark(dark)
        self._layout_pads()

    def set_dark(self, dark: bool) -> None:
        self.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)

    def update_bindings(self, bindings: dict[str, Binding]) -> None:
        """Reflect each pad's bound action as a big icon instead of the bare control id."""
        for control, button in self._pads.items():
            binding = bindings.get(control)
            if binding is None:
                button.setText(self._labels.get(control, control.upper()))
                button.setToolTip("")
            else:
                glyph = ACTION_GLYPHS.get(binding.action, "")
                custom_label = self._labels.get(control)
                button.setText(f"{glyph}\n{custom_label}" if custom_label else glyph or control.upper())
                button.setToolTip(ACTION_LABELS.get(binding.action, binding.action))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_pads()

    def _layout_pads(self) -> None:
        rects = compute_pad_rects(
            self.width(), self.height(), cols=COLS, rows=ROWS, margin=MARGIN, spacing=SPACING
        )
        for control, rect in zip(PAD_ORDER, rects):
            self._pads[control].setGeometry(rect)
