from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from mpk_deck.config import ACCENT_HEX

_BORDER = "rgba(0,0,0,50)"


class BankIndicator(QLabel):
    """Shows the active bank's display name as a solid accent-colored badge.

    Opaque by design, not a translucent glass pill - the previous glass-pill
    treatment was unreadable in dark mode (its fill alpha gave no real contrast
    against the panel behind it). An opaque badge looks identical in both themes,
    so it needs no theme branching - set_accent is the only thing that changes
    its appearance now.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._accent_hex = ACCENT_HEX
        self.set_bank_name("")
        self._apply_style()

    def set_bank_name(self, name: str) -> None:
        self.setText(name)
        self.adjustSize()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: #ffffff; font-size: 11px; font-weight: 600; "
            f"background: {self._accent_hex}; border: 1px solid {_BORDER}; "
            f"border-radius: 8px; padding: 2px 8px; }}"
        )
