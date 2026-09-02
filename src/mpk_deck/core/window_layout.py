"""Enumerate / capture / restore the on-screen windows for a Workspace Layout.

Pure helpers (`match_window`, `clamp_rect_to_monitors`) are unit-tested.
`list_open_windows`, `capture_item`, `position_window` and `restore_layout` all
take injectable seams so the orchestration is fully covered without opening real
windows; the win32 / UIA implementations behind those seams are manual-verify.
"""

import logging
import subprocess
import time as _time
from dataclasses import dataclass
from pathlib import Path

from mpk_deck.core.browser_url import browser_kind
from mpk_deck.core.layout_store import Layout, LayoutItem

logger = logging.getLogger(__name__)

_MAX_TITLE = 40
_POLL_TIMEOUT_S = 8.0
_POLL_INTERVAL_S = 0.25
_SETTLE_S = 0.15


@dataclass(frozen=True)
class OpenWindow:
    hwnd: int
    title: str
    exe_path: str
    rect: tuple[int, int, int, int]  # x, y, width, height (physical px, virtual-screen coords)
    maximized: bool


def _basename(path: str) -> str:
    return Path(path).name.lower()


def _short_title(title: str) -> str:
    return title.rsplit(" - ", 1)[-1].strip()[:_MAX_TITLE]


# --------------------------------------------------------------------------- #
# matching an already-open window to a layout item                            #
# --------------------------------------------------------------------------- #


def match_window(item: LayoutItem, windows: list[OpenWindow]) -> int | None:
    """The hwnd of an open window this item should be *repositioned* into (rather
    than launching a duplicate), or None. See design doc §9.3."""
    if item.kind == "program":
        target = _basename(item.path)
        cands = [w for w in windows if _basename(w.exe_path) == target]
    else:  # url
        want = item.browser
        cands = [w for w in windows if _browser_ok(w, want)]

    if not cands:
        return None
    if item.title_match:
        tm = item.title_match.lower()
        titled = [w for w in cands if tm in w.title.lower()]
        if titled:
            return titled[0].hwnd
        if item.kind == "url":
            return None  # a URL item must not hijack an unrelated browser window
        return cands[0].hwnd
    if item.kind == "url" and len(cands) > 1:
        return None  # ambiguous - open a fresh window instead
    return cands[0].hwnd


def _browser_ok(window: OpenWindow, want: str) -> bool:
    kind = browser_kind(window.exe_path)
    if kind is None:
        return False
    return True if want == "default" else kind == want


# --------------------------------------------------------------------------- #
# clamping a saved rect onto a still-visible monitor                          #
# --------------------------------------------------------------------------- #


def clamp_rect_to_monitors(
    rect: tuple[int, int, int, int], monitors: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int]:
    """Move / shrink `rect` so it lies inside the monitor work-area nearest its
    centre. A no-op when `rect` already fits a monitor."""
    x, y, w, h = rect
    if not monitors:
        return rect
    cx, cy = x + w / 2, y + h / 2

    def _dist(m: tuple[int, int, int, int]) -> float:
        mx, my, mw, mh = m
        return (cx - (mx + mw / 2)) ** 2 + (cy - (my + mh / 2)) ** 2

    mx, my, mw, mh = min(monitors, key=_dist)
    w = min(w, mw)
    h = min(h, mh)
    x = max(mx, min(x, mx + mw - w))
    y = max(my, min(y, my + mh - h))
    return (x, y, w, h)


# --------------------------------------------------------------------------- #
# enumerate + capture (win32; seam-injected)                                  #
# --------------------------------------------------------------------------- #


def list_open_windows(*, resolver=None) -> list[OpenWindow]:
    if resolver is not None:
        return resolver()
    return _win32_list_open_windows()


def _win32_list_open_windows() -> list[OpenWindow]:
    import ctypes
    from ctypes import wintypes

    import win32con
    import win32gui
    import win32process

    own_pid = ctypes.windll.kernel32.GetCurrentProcessId()
    results: list[OpenWindow] = []

    def _exe_path(pid: int) -> str:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
            return ""
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def _cloaked(hwnd: int) -> bool:
        DWMWA_CLOAKED = 14
        val = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            return False
        return val.value != 0

    def _cb(hwnd, _lparam):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        if win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW:
            return True
        if _cloaked(hwnd):
            return True
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left <= 0 or bottom - top <= 0:
            return True
        _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == own_pid:
            return True
        placement = win32gui.GetWindowPlacement(hwnd)
        results.append(
            OpenWindow(
                hwnd=hwnd,
                title=title,
                exe_path=_exe_path(pid),
                rect=(left, top, right - left, bottom - top),
                maximized=placement[1] == win32con.SW_SHOWMAXIMIZED,
            )
        )
        return True

    win32gui.EnumWindows(_cb, None)
    return results


def capture_item(window: OpenWindow, *, url_reader=None) -> LayoutItem:
    reader = url_reader if url_reader is not None else _default_url_reader
    kind = browser_kind(window.exe_path)
    if kind is not None:
        return LayoutItem(
            kind="url",
            url=reader(window.hwnd) or "",
            browser=kind,
            rect=window.rect,
            maximized=window.maximized,
            title_match=_short_title(window.title),
        )
    return LayoutItem(
        kind="program",
        path=window.exe_path,
        rect=window.rect,
        maximized=window.maximized,
        title_match=_short_title(window.title),
    )


def _default_url_reader(hwnd: int) -> str | None:
    from mpk_deck.core.browser_url import active_tab_url

    return active_tab_url(hwnd)


# --------------------------------------------------------------------------- #
# position + restore                                                          #
# --------------------------------------------------------------------------- #


def position_window(hwnd: int, rect: tuple[int, int, int, int], maximized: bool) -> None:
    try:
        import win32con
        import win32gui

        monitors = _monitor_work_areas()
        x, y, w, h = clamp_rect_to_monitors(rect, monitors) if monitors else rect
        show = win32con.SW_SHOWMAXIMIZED if maximized else win32con.SW_SHOWNORMAL
        win32gui.SetWindowPlacement(hwnd, (0, show, (-1, -1), (-1, -1), (x, y, x + w, y + h)))
        if not maximized:
            win32gui.SetWindowPos(
                hwnd, 0, x, y, w, h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            )
    except Exception:
        logger.warning("position_window failed for hwnd %s", hwnd, exc_info=True)


def _monitor_work_areas() -> list[tuple[int, int, int, int]]:
    try:
        import win32api

        areas = []
        for handle, _dc, _rect in win32api.EnumDisplayMonitors():
            left, top, right, bottom = win32api.GetMonitorInfo(handle)["Work"]
            areas.append((left, top, right - left, bottom - top))
        return areas
    except Exception:
        return []


def restore_layout(
    layout: Layout,
    *,
    window_lister=None,
    launcher=None,
    positioner=None,
    sleep=None,
) -> None:
    """Open + position every item of `layout`. Safe on a worker thread (it
    launches apps and polls for windows for several seconds)."""
    lister = window_lister or list_open_windows
    launch = launcher or _default_launch
    place = positioner or position_window
    nap = sleep or _time.sleep

    for i, item in enumerate(layout.items):
        hwnd = match_window(item, lister())
        if hwnd is None:
            launch(item)
            nap(0.2 * i)  # small stagger between launches
            hwnd = _poll_for_window(item, lister, nap)
        if hwnd is None:
            logger.warning("restore_layout: no window for %r", item)
            continue
        place(hwnd, item.rect, item.maximized)
        nap(_SETTLE_S)
        place(hwnd, item.rect, item.maximized)  # browsers/Electron re-lay-out just after show


def _poll_for_window(item: LayoutItem, lister, nap) -> int | None:
    waited = 0.0
    while waited < _POLL_TIMEOUT_S:
        hwnd = match_window(item, lister())
        if hwnd is not None:
            return hwnd
        nap(_POLL_INTERVAL_S)
        waited += _POLL_INTERVAL_S
    return None


def _default_launch(item: LayoutItem) -> None:
    try:
        if item.kind == "program":
            if item.path and Path(item.path).exists():
                subprocess.Popen([item.path])
            else:
                logger.warning("restore: program not found: %s", item.path)
            return
        if not item.url:
            logger.warning("restore: url item has no url, skipping launch")
            return
        exe = _resolve_browser_exe(item.browser)
        if exe:
            subprocess.Popen([exe, "--new-window", item.url])
        else:
            import webbrowser

            webbrowser.open(item.url)
    except Exception:
        logger.warning("restore: launch failed for %r", item, exc_info=True)


def _resolve_browser_exe(browser: str) -> str | None:
    if browser == "default":
        return None
    want = {"chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe"}.get(browser)
    if not want:
        return None
    try:
        from mpk_deck.core.program_finder import list_installed_programs

        for program in list_installed_programs():
            if _basename(program.path) == want:
                return program.path
    except Exception:
        logger.debug("program_finder lookup failed", exc_info=True)
    for guess in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
    ):
        if _basename(guess) == want and Path(guess).exists():
            return guess
    return None
