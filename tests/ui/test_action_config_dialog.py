import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from mpk_deck.core.action_registry import Binding
from mpk_deck.ui.action_config_dialog import ACTION_CHOICES, ActionConfigDialog, control_display_id


@pytest.fixture(autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def test_control_display_id():
    assert control_display_id("pad_3") == "PAD 3"
    assert control_display_id("knob_2") == "KNOB 2"
    assert control_display_id("joystick_x") == "JOYSTICK X"


def test_every_action_maps_to_an_existing_stack_page():
    dialog = ActionConfigDialog("pad_1")
    for action, _glyph, _label in ACTION_CHOICES:
        assert 0 <= dialog._page_for_action[action] < dialog._param_stack.count()


def test_selecting_scroll_shows_the_sensitivity_page_not_bank_name():
    # Regression: the old code set the stack index to the action-list row, so
    # "Scroll Horizontal" landed on the bank-name page.
    dialog = ActionConfigDialog("knob_2")
    dialog._select_action("scroll_horizontal")
    scroll_page = dialog._param_stack.currentIndex()
    dialog._select_action("scroll_vertical")
    assert dialog._param_stack.currentIndex() == scroll_page
    dialog._select_action("switch_bank")
    assert dialog._param_stack.currentIndex() != scroll_page


def test_scroll_binding_round_trips_through_the_slider():
    existing = Binding(control="joystick_x", type="continuous", action="scroll_horizontal", params={"sensitivity": 2.5})
    dialog = ActionConfigDialog("joystick_x", existing)
    assert dialog._sensitivity_slider.value() == 25
    result = dialog.result_binding()
    assert result.action == "scroll_horizontal"
    assert result.params["sensitivity"] == pytest.approx(2.5)


def test_launch_program_binding_round_trips():
    existing = Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x/chrome.exe"})
    dialog = ActionConfigDialog("pad_1", existing)
    assert dialog._current_action() == "launch_program"
    assert dialog.result_binding().params["path"] == "C:/x/chrome.exe"


def test_switch_bank_binding_locks_the_other_tiles():
    existing = Binding(control="key_0", type="trigger", action="switch_bank", params={"bank_id": "bank_a"})
    dialog = ActionConfigDialog("key_0", existing, bank_names={"bank_a": "Home"})
    assert dialog._tiles["launch_program"].isEnabled() is False
    assert dialog._tiles["switch_bank"].isEnabled() is True
    assert dialog.result_binding().action == "switch_bank"
    assert dialog.result_bank_name() == "Home"


def test_new_binding_defaults_to_first_action():
    dialog = ActionConfigDialog("pad_5")
    assert dialog._current_action() == ACTION_CHOICES[0][0]


def test_label_field_prefills_and_round_trips():
    existing = Binding("pad_1", "trigger", "open_url", {"url": "https://x"}, label="내 링크")
    dialog = ActionConfigDialog("pad_1", existing)
    assert dialog._label_edit.text() == "내 링크"
    dialog._label_edit.setText("  새 이름  ")
    assert dialog.result_binding().label == "새 이름"  # trimmed


def test_empty_label_field_yields_empty_label():
    dialog = ActionConfigDialog("pad_1")
    dialog._select_action("open_url")
    assert dialog.result_binding().label == ""


def test_switch_bank_disables_the_label_and_icon_fields():
    dialog = ActionConfigDialog("pad_1")
    dialog._select_action("open_url")
    assert dialog._label_edit.isEnabled() is True
    dialog._select_action("switch_bank")
    assert dialog._label_edit.isEnabled() is False
    assert dialog._icon_ai_toggle.isEnabled() is False
    # and switch_bank never carries a label/icon out
    assert dialog.result_binding().label == ""
    assert dialog.result_binding().icon == ""


def test_custom_icon_loads_clears_and_round_trips():
    svg = '<circle cx="32" cy="32" r="16" fill="none" stroke="{accent}" stroke-width="6"/>'
    dialog = ActionConfigDialog("pad_1", Binding("pad_1", "trigger", "open_url", {"url": "u"}, icon=svg))
    assert dialog._custom_icon == svg
    assert dialog.result_binding().icon == svg
    dialog._clear_custom_icon()
    assert dialog._custom_icon == ""
    assert dialog.result_binding().icon == ""


def test_apply_layout_binding_round_trips(monkeypatch):
    from mpk_deck.core.layout_store import Layout
    import mpk_deck.ui.action_config_dialog as acd
    from mpk_deck.core.action_registry import Binding

    monkeypatch.setattr(acd, "load_layouts", lambda: {"coding": Layout(name="코딩", items=[])})
    existing = Binding("pad_1", "trigger", "apply_layout", {"layout_id": "coding"})
    dialog = acd.ActionConfigDialog("pad_1", existing)
    assert dialog._current_action() == "apply_layout"
    assert dialog.result_binding().params == {"layout_id": "coding"}


def test_apply_layout_with_no_layouts_yields_empty_id(monkeypatch):
    import mpk_deck.ui.action_config_dialog as acd

    monkeypatch.setattr(acd, "load_layouts", lambda: {})
    dialog = acd.ActionConfigDialog("pad_1")
    dialog._select_action("apply_layout")
    assert dialog.result_binding().params == {"layout_id": ""}


def test_apply_layout_keeps_the_label_field_enabled(monkeypatch):
    import mpk_deck.ui.action_config_dialog as acd

    monkeypatch.setattr(acd, "load_layouts", lambda: {})
    dialog = acd.ActionConfigDialog("pad_1")
    dialog._select_action("apply_layout")
    assert dialog._label_edit.isEnabled() is True
