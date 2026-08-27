from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

# Same glass-chip palette as MiniView's QPushButtons, for a readable pill regardless of
# what's behind it (plain text with no backing was unreadable in dark mode - see history).
_LIGHT = {"fill": "rgba(255,255,255,140)", "border": "rgba(120,120,140,90)", "text": "#23242b"}
_DARK = {"fill": "rgba(255,255,255,18)", "border": "rgba(255,255,255,38)", "text": "#f2f4f8"}


class BankIndicator(QLabel):
    """Shows the active bank's display name as a small pill chip. Theme-aware, purely informational."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        colors = _DARK if self._dark else _LIGHT
        self.setStyleSheet(
            f"QLabel {{ color: {colors['text']}; font-size: 11px; font-weight: 600; "
            f"background: {colors['fill']}; border: 1px solid {colors['border']}; "
            f"border-radius: 8px; padding: 2px 8px; }}"
        )
