import logging
import subprocess
import webbrowser

logger = logging.getLogger(__name__)


def launch_program(params: dict) -> None:
    """Launch an external program by path.

    Expected params:
        path (str): Absolute or relative path to executable
    """
    path = params.get("path")
    if not path:
        logger.warning("launch_program: missing 'path' param")
        return
    subprocess.Popen([path])


def open_url(params: dict) -> None:
    """Open a URL in the default web browser.

    Expected params:
        url (str): URL to open
    """
    url = params.get("url")
    if not url:
        logger.warning("open_url: missing 'url' param")
        return
    webbrowser.open(url)


def focus_window(params: dict, *, finder=None) -> None:
    """Focus a window by title substring.

    Expected params:
        title_contains (str): Substring to match in window title (case-insensitive)

    Args:
        params: Parameter dict
        finder: Optional custom finder function for testing. Defaults to _default_find_and_focus.
    """
    title_substring = params.get("title_contains")
    if not title_substring:
        logger.warning("focus_window: missing 'title_contains' param")
        return
    find = finder or _default_find_and_focus
    find(title_substring)


def _default_find_and_focus(title_substring: str) -> None:
    """Default implementation: find and focus window using win32gui.

    Lazily imports win32gui so the module loads even if pywin32 isn't installed.
    """
    import win32gui

    def _callback(hwnd: int, results: list[int]) -> None:
        if win32gui.IsWindowVisible(hwnd) and title_substring.lower() in win32gui.GetWindowText(hwnd).lower():
            results.append(hwnd)

    results: list[int] = []
    win32gui.EnumWindows(_callback, results)
    if results:
        win32gui.SetForegroundWindow(results[0])
    else:
        logger.info("focus_window: no window matching %r", title_substring)
