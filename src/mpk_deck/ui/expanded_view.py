from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMenu, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX, ACCENT_RGB
from mpk_deck.ui.joystick_geometry import clamp_deflection
from mpk_deck.ui.keybed import NUM_KEYS, compute_keybed_rects, is_black_key
from mpk_deck.ui.mini_view import PadButton
from mpk_deck.ui.scaling import compute_scale
from mpk_deck.ui.window_grip import WindowGripMixin

PAD_LABELS_TOP = ["pad_5", "pad_6", "pad_7", "pad_8"]
PAD_LABELS_BOTTOM = ["pad_1", "pad_2", "pad_3", "pad_4"]
KNOB_LABELS_TOP = ["knob_1", "knob_2", "knob_3", "knob_4"]
KNOB_LABELS_BOTTOM = ["knob_5", "knob_6", "knob_7", "knob_8"]

ASPECT = 312 / 184
BORDER_VISUAL = 2  # thin visible edge-light inside the wider (window_grip.BORDER) grab zone
BASE_WIDTH = 480  # reference width the spec's fixed-px control sizes were measured at

LEFT_BUTTONS = [
    ("arp_on_off", "ON", "Arp On/Off"),
    ("tap_tempo", "TAP", "Tap Tempo"),
    ("octave_down", "OCT▼", "Octave Down"),
    ("octave_up", "OCT▲", "Octave Up"),
    ("full_level", "FULL", "Full Level"),
    ("note_repeat", "RPT", "Note Repeat"),
]
RIGHT_BUTTONS = [
    ("bank_ab", "BANK", "Bank A/B"),
    ("cc", "CC", "CC"),
    ("prog_change", "CHG", "Prog Change"),
    ("prog_select", "SEL", "Prog Select"),
]
GROUPED_RIGHT_BUTTONS = ["bank_ab", "cc", "prog_change"]  # spec: bordered as one group, SEL set apart

BASE_JOYSTICK_D = 40
BASE_BTN_W, BASE_BTN_H = 34, 16
BASE_BTN_FONT = 7
BASE_PAD_FONT = 9
BASE_KNOB_D = 24
BASE_KNOB_FONT = 8

# Matches MiniView's palette so both views read as one design system.
_LIGHT = {
    "fill": "rgba(255,255,255,140)",
    "fill_hover": "rgba(255,255,255,190)",
    "fill_pressed": "rgba(220,225,240,190)",
    "border": "rgba(120,120,140,90)",
    "text": "#23242b",
}
_DARK = {
    "fill": "rgba(255,255,255,18)",
    "fill_hover": "rgba(255,255,255,34)",
    "fill_pressed": "rgba(255,255,255,10)",
    "border": "rgba(255,255,255,38)",
    "text": "#f2f4f8",
}
# Keybed colors are theme-tinted but always readable as "black key vs white key",
# independent of app theme (a piano keybed reads by its own convention, not the app's).
_KEY_COLORS = {
    True: {  # dark theme
        "white": ("#e8e6df", "#33322c"),
        "black": ("#14161c", f"rgba({ACCENT_RGB},140)"),
    },
    False: {  # light theme
        "white": ("#fbfbfa", "#c9c6bd"),
        "black": ("#2b2620", f"rgba({ACCENT_RGB},140)"),
    },
}


class _DebouncedKey(QFrame):
    """A keybed key: single click activates (debounced), double click configures.

    QFrame has no QAbstractButton `clicked` signal to build on, so this mirrors
    PadButton's (mini_view.py) timer-based debounce directly on the raw mouse events.
    """

    activated = Signal()
    configure_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start(QApplication.doubleClickInterval())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._click_timer.stop()
        self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)


class JoystickWidget(QFrame):
    """Visual-only joystick indicator. Mouse drag previews the handle position but
    never triggers a scroll - the OS cursor sits on this widget while dragging, so a
    real scroll here would land on mpk-deck's own window, not whatever app the user
    is working in (see docs/superpowers/specs/2026-08-28-joystick-scroll-design.md).
    Real hardware input drives both the visual position (via set_deflection, called
    from MainWindow's on_continuous callback) and the actual scroll (via ActionEngine,
    entirely outside this widget)."""

    axis_configure_requested = Signal(str)  # "joystick_x" or "joystick_y"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._handle = QFrame(self)
        self._x = 0.0
        self._y = 0.0

    def set_deflection(self, x: float, y: float) -> None:
        self._x = max(-1.0, min(1.0, x))
        self._y = max(-1.0, min(1.0, y))
        self._reposition_handle()

    def apply_style(self, colors: dict[str, str], diameter: int) -> None:
        self.setFixedSize(diameter, diameter)
        self.setStyleSheet(
            f"QFrame {{ background: {colors['fill']}; border: 2px solid {ACCENT_HEX}; "
            f"border-radius: {diameter // 2}px; }}"
        )
        self._handle.setStyleSheet(f"QFrame {{ background: {ACCENT_HEX}; border-radius: 999px; }}")
        self._reposition_handle()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._reposition_handle()

    def _reposition_handle(self) -> None:
        base_r = self.width() / 2
        handle_d = max(1, round(self.width() * 0.4))
        handle_r = handle_d / 2
        self._handle.setFixedSize(handle_d, handle_d)
        cx = base_r + self._x * (base_r - handle_r) - handle_r
        cy = base_r + self._y * (base_r - handle_r) - handle_r
        self._handle.move(round(cx), round(cy))

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from_mouse(event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_from_mouse(event.position())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.set_deflection(0.0, 0.0)
        super().mouseReleaseEvent(event)

    def _drag_from_mouse(self, pos) -> None:
        cx, cy = self.width() / 2, self.height() / 2
        x, y = clamp_deflection(pos.x() - cx, pos.y() - cy, self.width() / 2)
        self.set_deflection(x, y)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        menu = QMenu(self)
        x_action = menu.addAction("Horizontal (joystick_x)")
        y_action = menu.addAction("Vertical (joystick_y)")
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is x_action:
            self.axis_configure_requested.emit("joystick_x")
        elif chosen is y_action:
            self.axis_configure_requested.emit("joystick_y")
        super().mouseDoubleClickEvent(event)


def _button_qss(colors: dict[str, str], font_px: float, radius: float) -> str:
    return (
        f"QPushButton {{ background: {colors['fill']}; border: 1px solid {colors['border']}; "
        f"border-radius: {radius:.0f}px; color: {colors['text']}; font-size: {font_px:.0f}px; "
        f"font-weight: 600; padding: 0px; margin: 0px; }}"
        f"QPushButton:hover {{ background: {colors['fill_hover']}; }}"
        f"QPushButton:pressed {{ background: {colors['fill_pressed']}; border: 1px solid {ACCENT_HEX}; }}"
    )


class ExpandedView(WindowGripMixin, QWidget):
    control_activated = Signal(str)
    control_configure_requested = Signal(str)

    def __init__(self, dark: bool = False, parent=None) -> None:
        super().__init__(parent, aspect=ASPECT, min_width=BASE_WIDTH)
        self.setObjectName("expandedPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(BASE_WIDTH, 284)  # keeps the 312:184 aspect ratio roughly intact
        self._dark = dark

        self._joystick = JoystickWidget(self)
        self._joystick.axis_configure_requested.connect(self.control_configure_requested.emit)

        self._buttons: dict[str, PadButton] = {}
        for control, text, tooltip in LEFT_BUTTONS + RIGHT_BUTTONS:
            btn = PadButton(text, self)
            btn.setToolTip(tooltip)
            btn.activated.connect(lambda c=control: self.control_activated.emit(c))
            btn.configure_requested.connect(lambda c=control: self.control_configure_requested.emit(c))
            self._buttons[control] = btn

        self._bank_group = QFrame(self)
        self._bank_group.lower()

        self._pads: dict[str, PadButton] = {}
        for control in PAD_LABELS_TOP + PAD_LABELS_BOTTOM:
            btn = PadButton(control.upper(), self)
            btn.activated.connect(lambda c=control: self.control_activated.emit(c))
            btn.configure_requested.connect(lambda c=control: self.control_configure_requested.emit(c))
            self._pads[control] = btn

        self._knobs: dict[str, QLabel] = {}
        for control in KNOB_LABELS_TOP + KNOB_LABELS_BOTTOM:
            lbl = QLabel(control.split("_")[1].upper(), self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._knobs[control] = lbl

        # 25 keys (15 white + 10 black), C to C over 2 octaves + 1 — matches the physical keybed.
        self._keys: dict[int, _DebouncedKey] = {}
        for i in range(NUM_KEYS):
            key = _DebouncedKey(self)
            key.activated.connect(lambda k=i: self.control_activated.emit(f"key_{k}"))
            key.configure_requested.connect(lambda k=i: self.control_configure_requested.emit(f"key_{k}"))
            self._keys[i] = key

        self.set_dark(dark)  # also lays out controls

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        bg = (
            "rgba(20,22,28,217)"
            if dark
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,120), "
            "stop:1 rgba(235,240,255,150))"  # matches MiniView's white glass, not accent-tinted
        )
        border_alpha = 100 if dark else 130
        self.setStyleSheet(
            f"QWidget#expandedPanel {{ background: {bg}; border-radius: 16px; "
            f"border: {BORDER_VISUAL}px solid rgba({ACCENT_RGB},{border_alpha}); }}"
        )
        self._bank_group.setStyleSheet(
            f"QFrame {{ border: 1px solid rgba({ACCENT_RGB},170); border-radius: 4px; "
            f"background: rgba({ACCENT_RGB},18); }}"
        )
        self._layout_controls()

    def set_joystick_deflection(self, x: float, y: float) -> None:
        self._joystick.set_deflection(x, y)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_controls()

    def _layout_controls(self) -> None:
        w, h = self.width(), self.height()
        scale = compute_scale(w, base_width=BASE_WIDTH)
        colors = _DARK if self._dark else _LIGHT

        btn_w, btn_h = round(BASE_BTN_W * scale), round(BASE_BTN_H * scale)
        btn_font = BASE_BTN_FONT * scale
        joy_d = round(BASE_JOYSTICK_D * scale)
        pad_font = BASE_PAD_FONT * scale
        knob_d = round(BASE_KNOB_D * scale)
        knob_font = BASE_KNOB_FONT * scale

        self._joystick.apply_style(colors, joy_d)

        btn_qss = _button_qss(colors, btn_font, radius=4 * scale)
        for control, btn in self._buttons.items():
            btn.setStyleSheet(btn_qss)
            btn.setFixedSize(btn_w, btn_h)

        pad_qss = _button_qss(colors, pad_font, radius=12 * scale)
        for btn in self._pads.values():
            btn.setStyleSheet(pad_qss)

        knob_qss = (
            f"QLabel {{ background: {colors['fill']}; border: 2px solid rgba({ACCENT_RGB},170); "
            f"border-radius: {knob_d // 2}px; color: {colors['text']}; font-size: {knob_font:.0f}px; "
            f"font-weight: 700; }}"
        )
        for lbl in self._knobs.values():
            lbl.setStyleSheet(knob_qss)
            lbl.setFixedSize(knob_d, knob_d)

        left_x = int(0.03 * w)
        left_y = int(0.04 * h)
        self._joystick.move(left_x, left_y)
        row_y = left_y + joy_d + 5
        for i in range(0, len(LEFT_BUTTONS), 2):
            a_control = LEFT_BUTTONS[i][0]
            b_control = LEFT_BUTTONS[i + 1][0]
            self._buttons[a_control].move(left_x, row_y)
            self._buttons[b_control].move(left_x + btn_w + 4, row_y)
            row_y += btn_h + 5

        pad_x, pad_y = int(0.18 * w), int(0.02 * h)
        pad_w, pad_h = int(0.42 * w) // 4, int(0.36 * h) // 2
        for i, control in enumerate(PAD_LABELS_TOP):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y, pad_w - 4, pad_h - 4)
        for i, control in enumerate(PAD_LABELS_BOTTOM):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y + pad_h, pad_w - 4, pad_h - 4)

        knob_x, knob_y = int(0.63 * w), int(0.04 * h)
        knob_cell_w = int(0.34 * w) // 4
        for i, control in enumerate(KNOB_LABELS_TOP):
            cx = knob_x + i * knob_cell_w + (knob_cell_w - knob_d) // 2
            self._knobs[control].move(cx, knob_y)
        knob_row_gap = round(14 * scale)
        for i, control in enumerate(KNOB_LABELS_BOTTOM):
            cx = knob_x + i * knob_cell_w + (knob_cell_w - knob_d) // 2
            self._knobs[control].move(cx, knob_y + knob_d + knob_row_gap)

        btn_row_x = knob_x + int(0.02 * w)
        btn_row_y = int(0.32 * h)
        bx = btn_row_x
        for control in GROUPED_RIGHT_BUTTONS:
            self._buttons[control].move(bx, btn_row_y)
            bx += btn_w + 4
        group_pad = 3
        content_right = bx - 4  # bx overshoots by the trailing gap after the last grouped button
        self._bank_group.setGeometry(
            btn_row_x - group_pad,
            btn_row_y - group_pad,
            content_right - btn_row_x + 2 * group_pad,
            btn_h + 2 * group_pad,
        )
        self._buttons["prog_select"].move(bx + 24 - 4, btn_row_y)

        key_x, key_y = int(0.015 * w), int(0.44 * h)
        key_w = int(0.97 * w)
        key_h = int(0.545 * h)
        white_rects, black_rects = compute_keybed_rects(key_w, key_h)
        white_semitones = [i for i in range(NUM_KEYS) if not is_black_key(i)]
        black_semitones = [i for i in range(NUM_KEYS) if is_black_key(i)]
        white_bg, white_border = _KEY_COLORS[self._dark]["white"]
        black_bg, black_border = _KEY_COLORS[self._dark]["black"]
        for semitone, rect in zip(white_semitones, white_rects):
            key = self._keys[semitone]
            key.setGeometry(rect.translated(key_x, key_y))
            key.setStyleSheet(f"QFrame {{ background: {white_bg}; border: 1px solid {white_border}; }}")
            key.raise_()
        for semitone, rect in zip(black_semitones, black_rects):
            key = self._keys[semitone]
            key.setGeometry(rect.translated(key_x, key_y))
            key.setStyleSheet(f"QFrame {{ background: {black_bg}; border: 1px solid {black_border}; }}")
            key.raise_()  # black keys sit visually on top of the white keys they overlap
