"""Pure aspect-locked resize math, keyed by the win32 HT* edge/corner codes from hit_test.py."""

from mpk_deck.ui.hit_test import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
)

# Zones whose drag delta drives width first (height is derived from aspect).
_WIDTH_DRIVEN = {HTLEFT, HTRIGHT, HTTOPLEFT, HTTOPRIGHT, HTBOTTOMLEFT, HTBOTTOMRIGHT}
# Zones that anchor the right edge (grow/shrink to the left).
_ANCHOR_RIGHT = {HTLEFT, HTTOPLEFT, HTBOTTOMLEFT}
# Zones that anchor the bottom edge (grow/shrink upward).
_ANCHOR_BOTTOM = {HTTOP, HTTOPLEFT, HTTOPRIGHT}


def compute_resized_rect(
    zone: int, *, x: int, y: int, w: int, h: int, dx: int, dy: int, aspect: float, min_w: int = 120
) -> tuple[int, int, int, int]:
    """Given a drag delta on one edge/corner, return the new (x, y, w, h) with width/height
    locked to `aspect`, anchored at the edge/corner opposite the one being dragged."""
    right, bottom = x + w, y + h

    if zone in _WIDTH_DRIVEN:
        raw_w = w - dx if zone in _ANCHOR_RIGHT else w + dx
        new_w = max(min_w, raw_w)
        new_h = round(new_w / aspect)
    else:
        raw_h = h - dy if zone in _ANCHOR_BOTTOM else h + dy
        new_h = max(round(min_w / aspect), raw_h)
        new_w = round(new_h * aspect)

    new_x = right - new_w if zone in _ANCHOR_RIGHT else x
    new_y = bottom - new_h if zone in _ANCHOR_BOTTOM else y
    return new_x, new_y, new_w, new_h
