from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

_LIGHT_TEXT = "#23242b"
_DARK_TEXT = "#f2f4f8"


class BankIndicator(QLabel):
    """Shows the active bank's display name. Theme-aware text color, purely informational."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dark = False
        self.set_bank_name("")
        self._apply_style()

    def set_bank_name(self, name: str) -> None:
        self.setText(name)
        self.adjustSize()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_style()

    def _apply_style(self) -> None:
        color = _DARK_TEXT if self._dark else _LIGHT_TEXT
        self.setStyleSheet(
            f"QLabel {{ color: {color}; font-size: 11px; font-weight: 600; background: transparent; }}"
        )
