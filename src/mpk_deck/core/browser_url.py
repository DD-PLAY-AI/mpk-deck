"""Browser detection + best-effort active-tab URL read for Workspace Layouts.

`browser_kind` is a pure basename check. `active_tab_url` walks the browser
window's UI Automation tree for the address bar - it never raises, returns None
on any failure, and the caller (the layout capture dialog) always offers a
manual URL field as the fallback. The UIA path is NOT unit-tested (needs a live
browser); verify it manually per the design doc.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BROWSERS = {"chrome.exe": "chrome", "msedge.exe": "edge", "firefox.exe": "firefox"}

# UIA constants (avoid importing the generated module just for these)
_UIA_EDIT_CONTROL_TYPE = 50004
_UIA_TOOLBAR_CONTROL_TYPE = 50021
_UIA_CONTROL_TYPE_PROPERTY = 30003
_UIA_VALUE_VALUE_PROPERTY = 30045
_TREE_SCOPE_DESCENDANTS = 4


def browser_kind(exe_path: str) -> str | None:
    """'.../chrome.exe' -> 'chrome', '.../msedge.exe' -> 'edge',
    '.../firefox.exe' -> 'firefox', anything else / '' -> None."""
    return _BROWSERS.get(Path(exe_path).name.lower()) if exe_path else None


def _normalise(text: str) -> str | None:
    """An address-bar value -> a URL, or None if it looks like a search term."""
    text = text.strip()
    if not text or " " in text or "." not in text:
        return None
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text


def active_tab_url(hwnd: int) -> str | None:
    """Best-effort UIA read of the active tab's address bar for the window
    `hwnd`. Chrome / Edge (Chromium) work; Firefox often does too. Returns None
    on any COM or lookup failure. Must run on a COM-initialised thread - the
    capture dialog runs on the Qt GUI thread, which is fine.
    """
    try:
        import comtypes.client

        uia_mod = comtypes.client.GetModule("UIAutomationCore.dll")
        uia = comtypes.client.CreateObject(uia_mod.CUIAutomation, interface=uia_mod.IUIAutomation)
        root = uia.ElementFromHandle(hwnd)
        if root is None:
            return None

        edit_cond = uia.CreatePropertyCondition(_UIA_CONTROL_TYPE_PROPERTY, _UIA_EDIT_CONTROL_TYPE)
        toolbar_cond = uia.CreatePropertyCondition(_UIA_CONTROL_TYPE_PROPERTY, _UIA_TOOLBAR_CONTROL_TYPE)

        # Restrict the search to the browser chrome's toolbars - the full window
        # tree also contains the rendered page, which is huge and slow to walk.
        scopes = []
        toolbars = root.FindAll(_TREE_SCOPE_DESCENDANTS, toolbar_cond)
        for i in range(min(toolbars.Length, 4)):
            scopes.append(toolbars.GetElement(i))
        if not scopes:
            scopes = [root]

        for scope in scopes:
            edits = scope.FindAll(_TREE_SCOPE_DESCENDANTS, edit_cond)
            for j in range(min(edits.Length, 6)):
                try:
                    value = edits.GetElement(j).GetCurrentPropertyValue(_UIA_VALUE_VALUE_PROPERTY)
                except Exception:  # noqa: BLE001 - a single flaky element must not abort the walk
                    continue
                if isinstance(value, str):
                    url = _normalise(value)
                    if url:
                        return url
        return None
    except Exception:  # noqa: BLE001 - contract: never raise
        logger.debug("active_tab_url failed for hwnd %s", hwnd, exc_info=True)
        return None
