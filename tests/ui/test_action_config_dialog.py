import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from mpk_deck.ui.action_config_dialog import ACTION_CHOICES, ActionConfigDialog


def _app():
    return QApplication.instance() or QApplication([])


def test_every_action_maps_to_an_existing_stack_page():
    _app()
    dialog = ActionConfigDialog("pad_1")
    page_count = dialog._param_stack.count()
    for action, _glyph, _label in ACTION_CHOICES:
        assert 0 <= dialog._page_for_action[action] < page_count


def test_selecting_scroll_horizontal_shows_the_sensitivity_page_not_bank_name():
    # Regression: the old code set the stack index to the action-list row, so
    # scroll_horizontal (row 4) landed on the bank-name page (page 4).
    _app()
    dialog = ActionConfigDialog("knob_2")
    dialog._select_action("scroll_horizontal")
    assert dialog._param_stack.currentWidget() is dialog._sensitivity_edit.parent()
    dialog._select_action("scroll_vertical")
    assert dialog._param_stack.currentWidget() is dialog._sensitivity_edit.parent()


def test_selecting_switch_bank_shows_the_bank_name_page():
    _app()
    dialog = ActionConfigDialog("pad_3")
    dialog._select_action("switch_bank")
    assert dialog._param_stack.currentWidget() is dialog._bank_name_edit.parent()
