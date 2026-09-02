import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from mpk_deck.core.action_registry import Binding
from mpk_deck.ui import action_icons
from mpk_deck.ui.action_icons import action_label, action_pixmap, program_name_from_path


@pytest.fixture(autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def test_program_name_from_path():
    assert program_name_from_path("C:/Program Files/Google/Chrome/Application/chrome.exe") == "Chrome"
    assert program_name_from_path("C:/x/KakaoTalk.exe") == "KakaoTalk"
    assert program_name_from_path("") == ""


def test_action_label_launch_program_uses_program_name():
    b = Binding("pad_1", "trigger", "launch_program", {"path": "C:/x/spotify.exe"})
    assert action_label(b) == "Spotify"


def test_action_label_launch_program_without_path_falls_back():
    assert action_label(Binding("pad_1", "trigger", "launch_program", {})) == "프로그램"


def test_action_label_switch_bank_resolves_the_bank_name():
    b = Binding("key_0", "trigger", "switch_bank", {"bank_id": "trd"})
    assert action_label(b, {"trd": "Trading"}) == "Trading"
    assert action_label(b) == "뱅크"  # no lookup -> generic


def test_action_label_known_actions():
    for action, expected in [
        ("open_url", "링크"),
        ("focus_window", "창 포커스"),
        ("set_system_volume", "음량"),
        ("scroll_vertical", "세로 스크롤"),
    ]:
        assert action_label(Binding("c", "trigger", action, {})) == expected


def test_action_pixmap_is_non_null_for_every_action():
    for action, _glyph, _label in [
        ("open_url", "", ""),
        ("focus_window", "", ""),
        ("set_system_volume", "", ""),
        ("scroll_horizontal", "", ""),
        ("scroll_vertical", "", ""),
        ("switch_bank", "", ""),
        ("launch_program", "", ""),  # no path -> painted fallback
    ]:
        pm = action_pixmap(Binding("c", "trigger", action, {}), 48, "#3a6df0")
        assert not pm.isNull()
        assert pm.size().width() == 48


def test_app_icon_pixmap_is_cached(monkeypatch):
    from PySide6.QtWidgets import QFileIconProvider

    calls = []
    orig_icon = QFileIconProvider.icon

    def counting_icon(self, info):
        calls.append(1)
        return orig_icon(self, info)

    monkeypatch.setattr(QFileIconProvider, "icon", counting_icon)
    action_icons._app_icon_cache.clear()
    p = r"C:\Windows\System32\notepad.exe"
    action_icons.app_icon_pixmap(p, 32)
    action_icons.app_icon_pixmap(p, 32)
    assert len(calls) == 1  # second call served from cache
