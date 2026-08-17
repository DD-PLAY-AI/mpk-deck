from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

PAD_LABELS_TOP = ["pad_5", "pad_6", "pad_7", "pad_8"]
PAD_LABELS_BOTTOM = ["pad_1", "pad_2", "pad_3", "pad_4"]
KNOB_LABELS_TOP = ["knob_1", "knob_2", "knob_3", "knob_4"]
KNOB_LABELS_BOTTOM = ["knob_5", "knob_6", "knob_7", "knob_8"]

LEFT_BUTTONS = [
    ("arp_on_off", "ON/OFF"),
    ("tap_tempo", "TAP"),
    ("octave_down", "OCT ▼"),
    ("octave_up", "OCT ▲"),
    ("full_level", "FULL LV"),
    ("note_repeat", "NOTE RPT"),
]
RIGHT_BUTTONS = [
    ("bank_ab", "BANK A/B"),
    ("cc", "CC"),
    ("prog_change", "PROG CHG"),
    ("prog_select", "PROG SEL"),
]

BTN_W, BTN_H = 34, 16


class ExpandedView(QWidget):
    control_clicked = Signal(str)

    def __init__(self, dark: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("expandedPanel")
        self.setMinimumSize(480, 284)  # keeps the 312:184 aspect ratio roughly intact

        self._joystick = QPushButton("JOY", self)
        self._joystick.setFixedSize(40, 40)
        self._joystick.clicked.connect(lambda: self.control_clicked.emit("joystick"))

        self._buttons: dict[str, QPushButton] = {}
        for control, text in LEFT_BUTTONS + RIGHT_BUTTONS:
            btn = QPushButton(text, self)
            btn.setFixedSize(BTN_W, BTN_H)
            btn.clicked.connect(lambda _checked=False, c=control: self.control_clicked.emit(c))
            self._buttons[control] = btn

        self._pads: dict[str, QPushButton] = {}
        for control in PAD_LABELS_TOP + PAD_LABELS_BOTTOM:
            btn = QPushButton(control.upper(), self)
            btn.clicked.connect(lambda _checked=False, c=control: self.control_clicked.emit(c))
            self._pads[control] = btn

        self._knobs: dict[str, QLabel] = {}
        for control in KNOB_LABELS_TOP + KNOB_LABELS_BOTTOM:
            lbl = QLabel(control.split("_")[1].upper(), self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._knobs[control] = lbl

        self._keys: list[QFrame] = []
        for _ in range(15):
            key = QFrame(self)
            key.setFrameShape(QFrame.Shape.Box)
            key.mousePressEvent = lambda _event, k=len(self._keys): self.control_clicked.emit(f"key_{k}")
            self._keys.append(key)

        self.set_dark(dark)
        self._layout_controls()

    def set_dark(self, dark: bool) -> None:
        bg = "rgba(20,22,28,217)" if dark else "rgba(120,110,255,90)"
        self.setStyleSheet(f"QWidget#expandedPanel {{ background: {bg}; border-radius: 16px; }}")

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_controls()

    def _layout_controls(self) -> None:
        w, h = self.width(), self.height()

        left_x = int(0.03 * w)
        left_y = int(0.04 * h)
        self._joystick.move(left_x, left_y)
        row_y = left_y + 40 + 5
        for i in range(0, len(LEFT_BUTTONS), 2):
            a_control, _ = LEFT_BUTTONS[i]
            b_control, _ = LEFT_BUTTONS[i + 1]
            self._buttons[a_control].move(left_x, row_y)
            self._buttons[b_control].move(left_x + BTN_W + 4, row_y)
            row_y += BTN_H + 5

        pad_x, pad_y = int(0.18 * w), int(0.02 * h)
        pad_w, pad_h = int(0.42 * w) // 4, int(0.36 * h) // 2
        for i, control in enumerate(PAD_LABELS_TOP):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y, pad_w - 4, pad_h - 4)
        for i, control in enumerate(PAD_LABELS_BOTTOM):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y + pad_h, pad_w - 4, pad_h - 4)

        knob_x, knob_y = int(0.63 * w), int(0.04 * h)
        knob_w = int(0.34 * w) // 4
        for i, control in enumerate(KNOB_LABELS_TOP):
            self._knobs[control].setGeometry(knob_x + i * knob_w, knob_y, knob_w - 4, 30)
        for i, control in enumerate(KNOB_LABELS_BOTTOM):
            self._knobs[control].setGeometry(knob_x + i * knob_w, knob_y + 44, knob_w - 4, 30)

        btn_row_x = knob_x + int(0.02 * w)
        btn_row_y = int(0.32 * h)
        bx = btn_row_x
        for control, _ in RIGHT_BUTTONS[:3]:
            self._buttons[control].move(bx, btn_row_y)
            bx += BTN_W + 4
        self._buttons["prog_select"].move(bx + 24 - 4, btn_row_y)

        key_x, key_y = int(0.015 * w), int(0.44 * h)
        key_w = int(0.97 * w) // len(self._keys)
        key_h = int(0.545 * h)
        for i, key in enumerate(self._keys):
            key.setGeometry(key_x + i * key_w, key_y, key_w, key_h)
