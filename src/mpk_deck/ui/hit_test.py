"""Pure edge/corner/interior classification for a frameless, resizable-by-edge window.

Reuses the standard win32 HT* codes (winuser.h) as zone identifiers - no pywin32
dependency needed here. Consumed by ui/window_grip.py's manual mouse handling,
not fed into a native WM_NCHITTEST message.
"""

HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17


def classify_hit(x: int, y: int, width: int, height: int, border: int, *, over_interactive: bool) -> int:
    """Classify a window-local point as a resize edge/corner, the draggable background, or a
    normal client-area click.

    `over_interactive` should be True when the point lands on a child widget
    that wants normal clicks (e.g. a pad button) rather than a window drag.
    """
    left = x < border
    right = x >= width - border
    top = y < border
    bottom = y >= height - border

    if top and left:
        return HTTOPLEFT
    if top and right:
        return HTTOPRIGHT
    if bottom and left:
        return HTBOTTOMLEFT
    if bottom and right:
        return HTBOTTOMRIGHT
    if left:
        return HTLEFT
    if right:
        return HTRIGHT
    if top:
        return HTTOP
    if bottom:
        return HTBOTTOM
    return HTCLIENT if over_interactive else HTCAPTION
