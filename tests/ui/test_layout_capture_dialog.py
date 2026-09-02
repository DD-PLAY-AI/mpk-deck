import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from mpk_deck.core.window_layout import OpenWindow
from mpk_deck.ui.layout_capture_dialog import LayoutCaptureDialog


@pytest.fixture(autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


_WINDOWS = [
    OpenWindow(1, "foo.py - Visual Studio Code", "C:/x/Code.exe", (10, 10, 800, 600), False),
    OpenWindow(2, "Claude - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900), True),
    OpenWindow(3, "New Tab - Google Chrome", "C:/x/chrome.exe", (100, 0, 500, 900), False),
]


def _dialog(tmp_path=None, monkeypatch=None):
    if tmp_path is not None:
        monkeypatch.setattr("mpk_deck.ui.layout_capture_dialog.LAYOUTS_PATH", tmp_path / "layouts.yaml")
    return LayoutCaptureDialog(
        window_lister=lambda: _WINDOWS,
        url_reader=lambda hwnd: "https://claude.ai" if hwnd == 2 else None,
    )


def test_rows_are_one_per_open_window():
    d = _dialog()
    assert len(d._rows) == 3
    assert d._rows[0].item.kind == "program"
    assert d._rows[1].item.kind == "url" and d._rows[1].url_edit is not None
    assert d._rows[0].url_edit is None


def test_browser_row_prefills_the_url_from_the_reader():
    d = _dialog()
    assert d._rows[1].url_edit.text() == "https://claude.ai"
    assert d._rows[2].url_edit.text() == ""


def test_cannot_save_a_ticked_browser_row_with_no_url():
    d = _dialog()
    d._name_edit.setText("코딩")
    for r in d._rows:
        r.checkbox.setChecked(True)  # row 3 has no URL
    assert d._can_save() is False
    d._rows[2].checkbox.setChecked(False)
    assert d._can_save() is True


def test_cannot_save_without_a_name():
    d = _dialog()
    d._rows[0].checkbox.setChecked(True)
    assert d._can_save() is False


def test_build_layout_from_ticked_rows(tmp_path, monkeypatch):
    d = _dialog(tmp_path, monkeypatch)
    d._name_edit.setText("코딩 셋업")
    d._rows[0].checkbox.setChecked(True)
    d._rows[1].checkbox.setChecked(True)
    layout = d._build_layout()
    assert layout.name == "코딩 셋업"
    assert [i.kind for i in layout.items] == ["program", "url"]
    assert layout.items[1].url == "https://claude.ai"
    assert layout.items[1].maximized is True


def test_save_persists_and_result_layout_id_is_set(tmp_path, monkeypatch):
    d = _dialog(tmp_path, monkeypatch)
    d._name_edit.setText("코딩")
    d._rows[0].checkbox.setChecked(True)
    d._on_save()
    from mpk_deck.core.layout_store import load_layouts

    saved = load_layouts(tmp_path / "layouts.yaml")
    assert d.result_layout_id() in saved
    assert saved[d.result_layout_id()].name == "코딩"
