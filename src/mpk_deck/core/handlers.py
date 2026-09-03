import logging
import subprocess
import threading
import time
import webbrowser

logger = logging.getLogger(__name__)


# Throttle state for continuous handlers whose side effect is expensive
# (WMI brightness is ~50-100ms/call and a knob emits tens of events/second).
# ponytail: module dict, fine for the handful of throttled controls we have.
_LAST_APPLIED: dict[str, float] = {}
_BRIGHTNESS_MIN_INTERVAL_S = 0.1  # ~10 Hz; brightness is coarse enough that a dropped tick is invisible


def _should_apply_now(key: str, min_interval_s: float, now: float) -> bool:
    last = _LAST_APPLIED.get(key)
    if last is not None and now - last < min_interval_s:
        return False
    _LAST_APPLIED[key] = now
    return True


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


def set_system_volume(params: dict, value: float, *, volume_setter=None) -> None:
    """`value` is a normalized 0.0-1.0 level (already converted by the caller)."""
    setter = volume_setter or _default_volume_setter
    setter(max(0.0, min(1.0, value)))


def set_display_brightness(
    params: dict, value: float, *, brightness_setter=None, now: float | None = None
) -> None:
    """`value` is a normalized 0.0-1.0 level (knob CC, already converted by translate()).
    Throttled to ~10 Hz; intermediate values are dropped (the knob keeps sending its
    current absolute position while it turns)."""
    if not _should_apply_now(
        "brightness", _BRIGHTNESS_MIN_INTERVAL_S, now if now is not None else time.monotonic()
    ):
        return
    setter = brightness_setter or _default_brightness_setter
    setter(round(max(0.0, min(1.0, value)) * 100))


def _default_brightness_setter(percent: int) -> None:
    import win32com.client

    wmi = win32com.client.GetObject(r"winmgmts:\\.\root\WMI")
    for method in wmi.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods"):
        method.WmiSetBrightness(1, percent)  # (timeout_seconds, brightness_percent)


def run_shell_command(params: dict, *, runner=None) -> None:
    """Fire-and-forget shell command on a pad/key press. No window, no output
    capture - same trust level as launch_program's arbitrary path."""
    command = (params.get("command") or "").strip()
    if not command:
        logger.info("run_shell_command: no command")
        return
    (runner or _default_command_runner)(command)


def _default_command_runner(command: str) -> None:
    subprocess.Popen(
        command,
        shell=True,
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


_MEDIA_VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2}


def media_key(params: dict, *, sender=None) -> None:
    """Send a media transport key to the OS. No-op-looking when nothing in the
    foreground consumes media keys - that is expected, not an error."""
    vk = _MEDIA_VK.get(params.get("key"))
    if vk is None:
        logger.info("media_key: unknown key %r", params.get("key"))
        return
    (sender or _default_media_key_sender)(vk)


def _default_media_key_sender(vk: int) -> None:
    import win32api
    import win32con

    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def _default_volume_setter(value: float) -> None:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(value, None)


def scroll_horizontal(params: dict, value: float, *, sender=None) -> None:
    """`value` in [-1.0, 1.0]: joystick X deflection, 0 = centered/no scroll.
    `params["sensitivity"]` (float, default 1.0) scales the notch count."""
    send = sender or _default_scroll_sender
    ticks = _scroll_notches(value, params.get("sensitivity", 1.0))
    if ticks:
        send(horizontal=True, notches=ticks)


def scroll_vertical(params: dict, value: float, *, sender=None) -> None:
    """Same as scroll_horizontal but for the vertical wheel."""
    send = sender or _default_scroll_sender
    ticks = _scroll_notches(value, params.get("sensitivity", 1.0))
    if ticks:
        send(horizontal=False, notches=ticks)


def _scroll_notches(value: float, sensitivity: float, *, max_notches: int = 3) -> int:
    """Pure: deflection + sensitivity -> whole wheel notches for one call. Linear in
    |value| so a light push scrolls slowly and a full push scrolls fast; sign gives
    direction."""
    return round(max(-1.0, min(1.0, value)) * sensitivity * max_notches)


def _default_scroll_sender(*, horizontal: bool, notches: int) -> None:
    """Real SendInput-class wheel injection - the OS treats it like a physical mouse
    wheel, unlike a PostMessage (which many apps, especially Chrome/Electron, ignore).
    Lands on whatever window the OS cursor is actually over - in real use that's
    always the app the user is working in, since mouse-drag on the on-screen joystick
    never calls this (see docs/superpowers/specs/2026-08-28-joystick-scroll-design.md)."""
    import win32api
    import win32con

    flag = win32con.MOUSEEVENTF_HWHEEL if horizontal else win32con.MOUSEEVENTF_WHEEL
    win32api.mouse_event(flag, 0, 0, notches * 120, 0)  # WHEEL_DELTA = 120 per notch


def apply_layout(params: dict, *, loader=None, restore=None) -> None:
    """Restore a saved workspace layout. The real work (launching apps, polling
    for their windows for several seconds) runs on a daemon thread so the GUI
    thread that dispatched this handler is never blocked."""
    layout_id = params.get("layout_id")
    if not layout_id:
        logger.info("apply_layout: no layout bound")
        return
    load = loader or _default_layout_loader
    layout = load().get(layout_id)
    if layout is None:
        logger.warning("apply_layout: layout %r not found", layout_id)
        return
    (restore or _spawn_restore)(layout)


def _default_layout_loader():
    from mpk_deck.core.layout_store import load_layouts

    return load_layouts()


def _spawn_restore(layout) -> None:
    from mpk_deck.core.window_layout import restore_layout

    threading.Thread(target=restore_layout, args=(layout,), daemon=True).start()
