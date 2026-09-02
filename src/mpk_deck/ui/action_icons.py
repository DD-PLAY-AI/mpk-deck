"""Icons and labels for a bound action, shown on the deck's pads/knobs/keys.

Resolution order for a pad/knob icon:
  1. launch_program with a real path -> the program's own Windows icon
  2. the action's built-in SVG glyph, rendered here in the deck's line language
     (one accent + one neutral tone, thin round strokes - not flat, not emoji)

The built-ins are SVG templates with {accent} / {neutral} slots, rendered through
QSvgRenderer - the same path C2's AI-made custom icons will use.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

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

# viewBox 0 0 64 64. {accent} = the action, {neutral} = the context it acts on.
_ACTION_SVG = {
    "open_url": (
        '<path d="M38 16 H30 a4 4 0 0 0 -4 4 V44 a4 4 0 0 0 4 4 H26" fill="none" stroke="{neutral}" '
        'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M26 44 h14 a4 4 0 0 0 4 -4 V30" fill="none" stroke="{neutral}" stroke-width="5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M32 32 L50 14 M40 14 H50 V24" fill="none" stroke="{accent}" stroke-width="5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "focus_window": (
        '<rect x="24" y="12" width="28" height="24" rx="4" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<rect x="12" y="26" width="30" height="26" rx="4" fill="none" stroke="{accent}" stroke-width="5"/>'
        '<path d="M14 33 h26" stroke="{accent}" stroke-width="6" stroke-linecap="round"/>'
    ),
    "set_system_volume": (
        '<path d="M12 26 h9 l12 -10 v32 l-12 -10 h-9 z" fill="{neutral}" stroke="{neutral}" '
        'stroke-width="4" stroke-linejoin="round"/>'
        '<path d="M40 24 a12 12 0 0 1 0 16" fill="none" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>'
        '<path d="M46 17 a22 22 0 0 1 0 30" fill="none" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>'
    ),
    "scroll_horizontal": (
        '<rect x="10" y="18" width="44" height="28" rx="5" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<path d="M20 32 H44 M25 25 L18 32 L25 39 M39 25 L46 32 L39 39" fill="none" stroke="{accent}" '
        'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "scroll_vertical": (
        '<rect x="18" y="10" width="28" height="44" rx="5" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<path d="M32 20 V44 M25 25 L32 18 L39 25 M25 39 L32 46 L39 39" fill="none" stroke="{accent}" '
        'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "switch_bank": (
        '<rect x="9" y="20" width="20" height="24" rx="4" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<rect x="35" y="20" width="20" height="24" rx="4" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<path d="M27 27 h10 M33 22 l5 5 l-5 5" fill="none" stroke="{accent}" stroke-width="4.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M37 41 h-10 M31 36 l-5 5 l5 5" fill="none" stroke="{accent}" stroke-width="4.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "launch_program": (
        '<rect x="12" y="12" width="40" height="40" rx="10" fill="none" stroke="{neutral}" stroke-width="5"/>'
        '<path d="M27 24 L42 32 L27 40 Z" fill="{accent}" stroke="{accent}" stroke-width="4" stroke-linejoin="round"/>'
    ),
}

# knob variant: accent mark only - the neutral frame is noise at ~18px and fights the needle
_ACTION_SVG_KNOB = {
    "open_url": (
        '<path d="M24 32 L46 10 M34 10 H46 V22" fill="none" stroke="{accent}" stroke-width="6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "focus_window": (
        '<rect x="14" y="20" width="30" height="26" rx="4" fill="none" stroke="{accent}" stroke-width="6"/>'
        '<path d="M16 28 h26" stroke="{accent}" stroke-width="7" stroke-linecap="round"/>'
    ),
    "set_system_volume": (
        '<path d="M14 26 h9 l12 -10 v32 l-12 -10 h-9 z" fill="{accent}" stroke="{accent}" stroke-width="4" '
        'stroke-linejoin="round"/>'
        '<path d="M42 22 a14 14 0 0 1 0 20" fill="none" stroke="{accent}" stroke-width="6" stroke-linecap="round"/>'
    ),
    "scroll_horizontal": (
        '<path d="M14 32 H50 M23 22 L13 32 L23 42 M41 22 L51 32 L41 42" fill="none" stroke="{accent}" '
        'stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "scroll_vertical": (
        '<path d="M32 14 V50 M22 23 L32 13 L42 23 M22 41 L32 51 L42 41" fill="none" stroke="{accent}" '
        'stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "switch_bank": (
        '<path d="M22 26 h20 M34 18 l9 8 l-9 8" fill="none" stroke="{accent}" stroke-width="6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M42 42 h-20 M30 34 l-9 8 l9 8" fill="none" stroke="{accent}" stroke-width="6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "launch_program": (
        '<path d="M24 18 L48 32 L24 46 Z" fill="{accent}" stroke="{accent}" stroke-width="5" stroke-linejoin="round"/>'
    ),
}

_app_icon_cache: dict[tuple[str, int], QPixmap] = {}


def program_name_from_path(path: str) -> str:
    """'C:/.../chrome.exe' -> 'Chrome'. Cheap - no Start Menu scan."""
    stem = Path(path).stem
    return stem[:1].upper() + stem[1:] if stem else path


def action_label(binding: Binding, bank_names: dict[str, str] | None = None) -> str:
    if binding.label:
        return binding.label
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


def render_svg_icon(svg_body: str, size: int, accent_hex: str, neutral_hex: str = _NEUTRAL) -> QPixmap:
    """Render an {accent}/{neutral}-templated 64x64 SVG body to a `size`px pixmap.
    Returns a blank (non-null) pixmap if the markup won't parse."""
    markup = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{svg_body}</svg>'
    ).replace("{accent}", accent_hex).replace("{neutral}", neutral_hex)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(markup.encode("utf-8"))
    if renderer.isValid():
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
    return pm


def action_pixmap(binding: Binding, size: int, accent_hex: str, *, for_knob: bool = False) -> QPixmap:
    """A `size`x`size` icon for this binding at the current accent."""
    if binding.action == "launch_program":
        path = binding.params.get("path", "")
        if path:
            pm = app_icon_pixmap(path, size)
            if pm is not None:
                return pm
    table = _ACTION_SVG_KNOB if for_knob else _ACTION_SVG
    body = table.get(binding.action) or _ACTION_SVG["launch_program"]
    return render_svg_icon(body, size, accent_hex)
