from mpk_deck.core.layout_store import Layout, LayoutItem
from mpk_deck.core.window_layout import (
    OpenWindow,
    capture_item,
    clamp_rect_to_monitors,
    list_open_windows,
    match_window,
    restore_layout,
)


def _win(hwnd, title, exe, rect=(0, 0, 100, 100), maximized=False):
    return OpenWindow(hwnd=hwnd, title=title, exe_path=exe, rect=rect, maximized=maximized)


# ---- match_window --------------------------------------------------------- #


def test_match_program_by_exe_basename():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1))
    wins = [_win(1, "x", "D:/other/Code.EXE"), _win(2, "y", "C:/z/notepad.exe")]
    assert match_window(item, wins) == 1


def test_match_program_prefers_title_match():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1), title_match="Project A")
    wins = [_win(1, "Project B - Code", "C:/Code.exe"), _win(2, "Project A - Code", "C:/Code.exe")]
    assert match_window(item, wins) == 2


def test_match_program_returns_none_when_absent():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1))
    assert match_window(item, [_win(1, "x", "C:/notepad.exe")]) is None


def test_match_url_by_browser_and_title():
    item = LayoutItem(kind="url", url="https://x", browser="chrome", rect=(0, 0, 1, 1), title_match="Claude")
    wins = [_win(1, "GitHub - Chrome", "C:/chrome.exe"), _win(2, "Claude - Chrome", "C:/chrome.exe")]
    assert match_window(item, wins) == 2


def test_match_url_without_title_and_multiple_candidates_returns_none():
    item = LayoutItem(kind="url", url="https://x", browser="chrome", rect=(0, 0, 1, 1))
    wins = [_win(1, "A - Chrome", "C:/chrome.exe"), _win(2, "B - Chrome", "C:/chrome.exe")]
    assert match_window(item, wins) is None


def test_match_url_default_browser_matches_any_chromium():
    item = LayoutItem(kind="url", url="https://x", browser="default", rect=(0, 0, 1, 1), title_match="Claude")
    assert match_window(item, [_win(1, "Claude - Edge", "C:/msedge.exe")]) == 1


# ---- clamp_rect_to_monitors --------------------------------------------- #


def test_clamp_rect_keeps_a_fully_visible_rect():
    assert clamp_rect_to_monitors((100, 100, 800, 600), [(0, 0, 1920, 1080)]) == (100, 100, 800, 600)


def test_clamp_rect_pulls_an_offscreen_rect_onto_the_nearest_monitor():
    x, y, w, h = clamp_rect_to_monitors((3000, 100, 800, 600), [(0, 0, 1920, 1080)])
    assert 0 <= x and x + w <= 1920 and 0 <= y and y + h <= 1080


def test_clamp_rect_shrinks_a_rect_bigger_than_the_monitor():
    x, y, w, h = clamp_rect_to_monitors((0, 0, 4000, 4000), [(0, 0, 1280, 720)])
    assert w <= 1280 and h <= 720


# ---- list_open_windows / capture_item ---------------------------------- #


def test_list_open_windows_uses_the_injected_resolver():
    fake = [_win(1, "A", "C:/a.exe")]
    assert list_open_windows(resolver=lambda: fake) == fake


def test_capture_item_program_window():
    w = _win(9, "foo.py - Visual Studio Code", "C:/x/Code.exe", (10, 20, 800, 600))
    item = capture_item(w, url_reader=lambda hwnd: None)
    assert item.kind == "program"
    assert item.path == "C:/x/Code.exe"
    assert item.rect == (10, 20, 800, 600)
    assert item.title_match == "Visual Studio Code"


def test_capture_item_browser_window_with_a_readable_url():
    w = _win(9, "Claude - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900), maximized=True)
    item = capture_item(w, url_reader=lambda hwnd: "https://claude.ai/code")
    assert item.kind == "url"
    assert item.url == "https://claude.ai/code"
    assert item.browser == "chrome"
    assert item.maximized is True


def test_capture_item_browser_window_without_a_readable_url_emits_empty_url():
    w = _win(9, "New Tab - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900))
    item = capture_item(w, url_reader=lambda hwnd: None)
    assert item.kind == "url"
    assert item.url == ""
    assert item.browser == "chrome"


# ---- restore_layout ---------------------------------------------------- #


def test_restore_positions_an_already_open_window_and_does_not_launch():
    item = LayoutItem(kind="program", path="C:/Code.exe", rect=(10, 10, 800, 600))
    open_win = _win(42, "Code", "C:/Code.exe")
    launched, positioned = [], []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lambda: [open_win],
        launcher=lambda it: launched.append(it),
        positioner=lambda hwnd, rect, mx: positioned.append((hwnd, rect, mx)),
        sleep=lambda _s: None,
    )
    assert launched == []
    assert positioned[0][0] == 42
    assert positioned[0][1] == (10, 10, 800, 600)


def test_restore_launches_then_polls_then_positions_a_missing_item():
    item = LayoutItem(kind="program", path="C:/Code.exe", rect=(5, 5, 400, 300))
    calls = {"n": 0}
    appears = _win(99, "Code", "C:/Code.exe")

    def lister():
        calls["n"] += 1
        return [] if calls["n"] <= 2 else [appears]

    launched, positioned = [], []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lister,
        launcher=lambda it: launched.append(it),
        positioner=lambda hwnd, rect, mx: positioned.append(hwnd),
        sleep=lambda _s: None,
    )
    assert launched == [item]
    assert positioned == [99, 99]  # positioned twice (immediately + after settle)


def test_restore_logs_and_continues_when_a_window_never_appears(caplog):
    item = LayoutItem(kind="program", path="C:/Missing.exe", rect=(0, 0, 1, 1))
    positioned = []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lambda: [],
        launcher=lambda it: None,
        positioner=lambda *a: positioned.append(a),
        sleep=lambda _s: None,
    )
    assert positioned == []
    assert "no window" in caplog.text.lower()
