from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX
from mpk_deck.core.action_registry import Binding
from mpk_deck.ui.accent import hex_to_rgb_str
from mpk_deck.ui.action_icons import action_label, action_pixmap
from mpk_deck.ui.grid_layout import compute_pad_rects
from mpk_deck.ui.window_grip import WindowGripMixin

PAD_ORDER = ["pad_5", "pad_6", "pad_7", "pad_8", "pad_1", "pad_2", "pad_3", "pad_4"]

COLS, ROWS = 4, 2
ASPECT = COLS / ROWS
MARGIN, SPACING = 20, 8
BORDER_VISUAL = 2  # thin visible edge-light inside the wider (BORDER) grab zone


def _light_qss(accent_hex: str, accent_rgb: str) -> str:
    return f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255,255,255,120), stop:1 rgba(235,240,255,150));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({accent_rgb},130);
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
QPushButton:pressed {{ background: rgba(220,225,240,190); border: 1px solid {accent_hex}; }}
"""


def _dark_qss(accent_hex: str, accent_rgb: str) -> str:
    return f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20,22,28,217), stop:1 rgba(10,12,16,191));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({accent_rgb},100);
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
QPushButton:pressed {{ background: rgba(255,255,255,10); border: 1px solid {accent_hex}; }}
"""


class PadButton(QPushButton):
    """A button that tells single clicks (trigger) apart from double clicks (configure).

    Also owns the accent-colored press glow (a QGraphicsDropShadowEffect kept
    attached permanently and toggled via setEnabled, rather than
    attached/detached per press - simpler and avoids effect-teardown timing
    issues). Shared by MiniView and ExpandedView, so the glow behavior is
    identical everywhere a pad/button reacts to a press.
    """

    activated = Signal()
    configure_requested = Signal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._binding_pixmap = None
        self._binding_label = ""
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)
        self.clicked.connect(self._on_clicked)
        self._accent_hex = ACCENT_HEX
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(16)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(self._accent_hex))
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self._glow.setEnabled(False))

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        self._glow.setColor(QColor(accent_hex))

    def _on_clicked(self) -> None:
        self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._click_timer.stop()
        self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._glow.setColor(QColor(self._accent_hex))
        self._glow.setEnabled(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._glow.setEnabled(False)
        super().mouseReleaseEvent(event)

    def flash(self) -> None:
        """Brief accent glow when the control fires from hardware - same look as a
        mouse press, since a MIDI trigger is momentary and has no release event."""
        self._glow.setColor(QColor(self._accent_hex))
        self._glow.setEnabled(True)
        self._flash_timer.start(180)

    def set_binding(self, pixmap, label: str) -> None:
        """Show the bound action as an icon over a label. `pixmap` None + empty
        label reverts to the plain text set via setText()."""
        self._binding_pixmap = pixmap
        self._binding_label = label
        if pixmap is not None or label:
            self.setText("")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        if self._binding_pixmap is None and not self._binding_label:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        has_label = bool(self._binding_label)
        icon_box = h * (0.52 if has_label else 0.7)
        if self._binding_pixmap is not None:
            side = min(icon_box, w * 0.7)
            scaled = self._binding_pixmap.scaled(
                round(side), round(side), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            top = (h * 0.62 - scaled.height()) / 2 if has_label else (h - scaled.height()) / 2
            painter.drawPixmap(round((w - scaled.width()) / 2), round(max(2, top)), scaled)
        if has_label:
            painter.setPen(self.palette().buttonText().color())
            font = painter.font()
            font.setPixelSize(max(8, round(h * 0.16)))
            painter.setFont(font)
            fm = QFontMetrics(font)
            text = fm.elidedText(self._binding_label, Qt.TextElideMode.ElideRight, round(w - 6))
            painter.drawText(QRectF(3, h * 0.6, w - 6, h * 0.36), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, text)


class MiniView(WindowGripMixin, QWidget):
    pad_activated = Signal(str)
    pad_configure_requested = Signal(str)

    def __init__(self, labels: dict[str, str] | None = None, dark: bool = False, parent=None) -> None:
        super().__init__(parent, aspect=ASPECT, min_width=240)
        self.setObjectName("miniPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._labels = labels or {}
        self._dark = dark
        self._accent_hex = ACCENT_HEX
        self._bindings: dict[str, Binding] = {}
        self._bank_names: dict[str, str] = {}
        self._layouts: dict = {}
        self._pads: dict[str, PadButton] = {}
        for control in PAD_ORDER:
            button = PadButton(self._labels.get(control, control.upper()), self)
            button.activated.connect(lambda c=control: self.pad_activated.emit(c))
            button.configure_requested.connect(lambda c=control: self.pad_configure_requested.emit(c))
            self._pads[control] = button
        self._apply_style()
        self._layout_pads()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_style()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        for pad in self._pads.values():
            pad.set_accent(accent_hex)
        self._apply_style()
        self.update_bindings(self._bindings, self._bank_names, self._layouts)  # icons bake the accent - repaint

    def flash_control(self, control: str) -> None:
        pad = self._pads.get(control)
        if pad is not None:
            pad.flash()

    def _apply_style(self) -> None:
        accent_rgb = hex_to_rgb_str(self._accent_hex)
        qss = _dark_qss(self._accent_hex, accent_rgb) if self._dark else _light_qss(self._accent_hex, accent_rgb)
        self.setStyleSheet(qss)

    def update_bindings(
        self,
        bindings: dict[str, Binding],
        bank_names: dict[str, str] | None = None,
        layouts: dict | None = None,
    ) -> None:
        """Reflect each pad's bound action as an icon over a readable label."""
        self._bindings = dict(bindings)
        self._bank_names = dict(bank_names or {})
        self._layouts = dict(layouts or {})
        for control, button in self._pads.items():
            binding = bindings.get(control)
            if binding is None:
                button.set_binding(None, "")
                button.setText(self._labels.get(control, control.upper()))
                button.setToolTip("")
            else:
                label = self._labels.get(control) or action_label(binding, self._bank_names, self._layouts)
                button.set_binding(action_pixmap(binding, 64, self._accent_hex), label)
                button.setToolTip(label)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_pads()

    def _layout_pads(self) -> None:
        rects = compute_pad_rects(
            self.width(), self.height(), cols=COLS, rows=ROWS, margin=MARGIN, spacing=SPACING
        )
        for control, rect in zip(PAD_ORDER, rects):
            self._pads[control].setGeometry(rect)
