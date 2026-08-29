from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel

from mpk_deck.config import ACCENT_HEX
from mpk_deck.ui.accent import hex_to_rgb_str

HINT_TEXT = "패드가 Bank B로 설정되어 있습니다 - 기기의 BANK 버튼으로 Bank A로 전환하세요."
VISIBLE_MS = 4000


class BankHint(QLabel):
    """Transient overlay shown when the MPK sends a Bank B pad note (44-47).
    Same MainWindow-child overlay pattern as BankIndicator; auto-hides."""

    def __init__(self, parent=None) -> None:
        super().__init__(HINT_TEXT, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWordWrap(False)
        self._accent_hex = ACCENT_HEX
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.set_accent(ACCENT_HEX)
        self.hide()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        rgb = hex_to_rgb_str(accent_hex)
        self.setStyleSheet(
            f"QLabel {{ background: rgba({rgb},235); color: #ffffff; "
            f"border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 600; }}"
        )
        self.adjustSize()

    def show_hint(self) -> None:
        self.adjustSize()
        self.show()
        self.raise_()
        self._hide_timer.start(VISIBLE_MS)
