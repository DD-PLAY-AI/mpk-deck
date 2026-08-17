from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

PAD_ORDER = ["pad_5", "pad_6", "pad_7", "pad_8", "pad_1", "pad_2", "pad_3", "pad_4"]

LIGHT_QSS = """
QWidget#miniPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(120,110,255,90), stop:1 rgba(60,180,255,64));
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,64);
}
QPushButton {
    background: rgba(255,255,255,36);
    border: 1px solid rgba(255,255,255,64);
    border-radius: 12px;
    color: white;
    font-size: 11px;
}
QPushButton:hover { background: rgba(255,255,255,64); }
"""

DARK_QSS = """
QWidget#miniPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20,22,28,217), stop:1 rgba(10,12,16,191));
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,26);
}
QPushButton {
    background: rgba(255,255,255,13);
    border: 1px solid rgba(255,255,255,26);
    border-radius: 12px;
    color: #d7dae0;
    font-size: 11px;
}
QPushButton:hover { background: rgba(255,255,255,26); }
"""


class MiniView(QWidget):
    pad_clicked = Signal(str)

    def __init__(self, labels: dict[str, str] | None = None, dark: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("miniPanel")
        self._labels = labels or {}
        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        for index, control in enumerate(PAD_ORDER):
            row, col = divmod(index, 4)
            button = QPushButton(self._labels.get(control, control.upper()))
            button.clicked.connect(lambda _checked=False, c=control: self.pad_clicked.emit(c))
            layout.addWidget(button, row, col)
        self.set_dark(dark)

    def set_dark(self, dark: bool) -> None:
        self.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)
