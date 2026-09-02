"""Icons and labels for a bound action, shown on the deck's pads/knobs/keys.

Resolution order for a pad/knob icon:
  1. a per-binding custom icon  (added in C2 - not here yet)
  2. launch_program with a real path -> the program's own Windows icon
  3. the action's built-in glyph, painted here in the deck's line language
     (thin strokes, one accent + one neutral tone - not flat, not emoji)
"""

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from mpk_deck.core.action_registry import Binding

ACTION_KO_LABEL = {
    "launch_program": "프로그램",
    "open_url": "링크",
    "focus_window": "창 포커스",
    "set_system_volume": "음량",
    "scroll_horizontal": "가로 스크롤",
    "scroll_vertical": "세로 스크롤",
    "switch_bank": "뱅크",
}

_NEUTRAL = "#8a8f9c"

_app_icon_cache: dict[tuple[str, int], QPixmap] = {}


def program_name_from_path(path: str) -> str:
    """'C:/.../chrome.exe' -> 'Chrome'. Cheap - no Start Menu scan."""
    stem = Path(path).stem
    return stem[:1].upper() + stem[1:] if stem else path


def action_label(binding: Binding, bank_names: dict[str, str] | None = None) -> str:
    if binding.action == "launch_program":
        path = binding.params.get("path", "")
        return program_name_from_path(path) if path else ACTION_KO_LABEL["launch_program"]
    if binding.action == "switch_bank":
        bank_id = binding.params.get("bank_id", "")
        return (bank_names or {}).get(bank_id) or ACTION_KO_LABEL["switch_bank"]
    return ACTION_KO_LABEL.get(binding.action, binding.action)


def app_icon_pixmap(path: str, size: int) -> QPixmap | None:
    key = (path, size)
    if key in _app_icon_cache:
        pm = _app_icon_cache[key]
        return pm if not pm.isNull() else None
    from PySide6.QtCore import QFileInfo
    from PySide6.QtWidgets import QFileIconProvider

    icon = QFileIconProvider().icon(QFileInfo(path))
    pm = icon.pixmap(size, size) if not icon.isNull() else QPixmap()
    _app_icon_cache[key] = pm
    return pm if not pm.isNull() else None


def action_pixmap(binding: Binding, size: int, accent_hex: str) -> QPixmap:
    """A `size`x`size` icon for this binding, at the current accent."""
    if binding.action == "launch_program":
        path = binding.params.get("path", "")
        if path:
            pm = app_icon_pixmap(path, size)
            if pm is not None:
                return pm
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_action_glyph(painter, binding.action, size, QColor(accent_hex), QColor(_NEUTRAL))
    painter.end()
    return pm


def paint_action_glyph(painter: QPainter, action: str, size: int, accent: QColor, neutral: QColor) -> None:
    """Draw the action's built-in glyph filling a `size`x`size` box at the origin."""
    s = size
    stroke = max(1.5, s * 0.08)
    accent_pen = QPen(accent, stroke)
    accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    accent_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    neutral_pen = QPen(neutral, stroke)
    neutral_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    neutral_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if action == "open_url":
        # two linked capsules on a diagonal
        for i, pen in ((0, neutral_pen), (1, accent_pen)):
            painter.setPen(pen)
            r = QRectF(s * (0.16 + i * 0.30), s * (0.30 + i * 0.14), s * 0.40, s * 0.26)
            painter.save()
            painter.translate(r.center())
            painter.rotate(-45)
            painter.translate(-r.center())
            painter.drawRoundedRect(r, s * 0.13, s * 0.13)
            painter.restore()

    elif action == "focus_window":
        body = QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.56)
        painter.setPen(neutral_pen)
        painter.drawRoundedRect(body, s * 0.06, s * 0.06)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(body.left(), body.top(), body.width(), s * 0.14), s * 0.06, s * 0.06)

    elif action == "set_system_volume":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(neutral)
        cone = QPainterPath()
        cone.moveTo(s * 0.14, s * 0.40)
        cone.lineTo(s * 0.30, s * 0.40)
        cone.lineTo(s * 0.46, s * 0.24)
        cone.lineTo(s * 0.46, s * 0.76)
        cone.lineTo(s * 0.30, s * 0.60)
        cone.lineTo(s * 0.14, s * 0.60)
        cone.closeSubpath()
        painter.drawPath(cone)
        painter.setPen(accent_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(s * 0.40, s * 0.28, s * 0.34, s * 0.44), -60 * 16, 120 * 16)
        painter.drawArc(QRectF(s * 0.40, s * 0.16, s * 0.54, s * 0.68), -55 * 16, 110 * 16)

    elif action in ("scroll_horizontal", "scroll_vertical"):
        painter.setPen(neutral_pen)
        if action == "scroll_horizontal":
            painter.drawLine(QPointF(s * 0.24, s * 0.5), QPointF(s * 0.76, s * 0.5))
            painter.setPen(accent_pen)
            painter.drawPolyline([QPointF(s * 0.30, s * 0.34), QPointF(s * 0.16, s * 0.5), QPointF(s * 0.30, s * 0.66)])
            painter.drawPolyline([QPointF(s * 0.70, s * 0.34), QPointF(s * 0.84, s * 0.5), QPointF(s * 0.70, s * 0.66)])
        else:
            painter.drawLine(QPointF(s * 0.5, s * 0.24), QPointF(s * 0.5, s * 0.76))
            painter.setPen(accent_pen)
            painter.drawPolyline([QPointF(s * 0.34, s * 0.30), QPointF(s * 0.5, s * 0.16), QPointF(s * 0.66, s * 0.30)])
            painter.drawPolyline([QPointF(s * 0.34, s * 0.70), QPointF(s * 0.5, s * 0.84), QPointF(s * 0.66, s * 0.70)])

    elif action == "switch_bank":
        painter.setPen(neutral_pen)
        painter.drawRoundedRect(QRectF(s * 0.16, s * 0.16, s * 0.52, s * 0.52), s * 0.08, s * 0.08)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(s * 0.32, s * 0.32, s * 0.52, s * 0.52), s * 0.08, s * 0.08)

    else:  # launch_program with no path, or an unknown action
        painter.setPen(accent_pen)
        painter.drawRoundedRect(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), s * 0.12, s * 0.12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        tri = QPainterPath()
        tri.moveTo(s * 0.42, s * 0.36)
        tri.lineTo(s * 0.66, s * 0.5)
        tri.lineTo(s * 0.42, s * 0.64)
        tri.closeSubpath()
        painter.drawPath(tri)


def action_qicon(binding: Binding, size: int, accent_hex: str) -> QIcon:
    return QIcon(action_pixmap(binding, size, accent_hex))
