import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from mpk_deck.ui.main_window import MainWindow


def test_midi_callbacks_reach_gui_thread(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("mpk_deck.ui.main_window.MPKController.start", lambda self: False)
    window = MainWindow()
    window._mode = "mini"
    window._apply_mode()

    worker = threading.Thread(
        target=lambda: (
            window._on_trigger("pad_1", True),
            window._on_joystick_continuous("joystick_y", 1.0),
        )
    )
    worker.start()
    worker.join()

    for _ in range(10):
        app.processEvents()

    assert window._mini_view._pads["pad_1"]._glow.isEnabled()
    # Y is negated for the widget: "push up" (value 1.0) moves the handle up (screen -y).
    assert window._expanded_view._joystick._y == -1.0
    assert window._expanded_view._knobs["knob_1"]._value == 0.0
    window.close()


def test_joystick_deadzone_snaps_small_values_to_zero() -> None:
    QApplication.instance() or QApplication([])
    import mpk_deck.ui.main_window as mw

    import unittest.mock as m
    with m.patch.object(mw.MPKController, "start", lambda self: False):
        window = MainWindow()
    window._apply_joystick_continuous("joystick_y", 0.03)  # inside the deadzone
    assert window._joystick_values["joystick_y"] == 0.0
    assert not window._joystick_timer.isActive()
    window._apply_joystick_continuous("joystick_y", 0.5)
    assert window._joystick_values["joystick_y"] == 0.5
    window.close()


def test_normal_binding_label_and_icon_round_trip_through_save(tmp_path, monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    import mpk_deck.ui.main_window as mw
    from mpk_deck.core.action_registry import Binding, load_config

    cfg_path = tmp_path / "actions.yaml"
    monkeypatch.setattr(mw, "DEFAULT_ACTIONS_PATH", str(cfg_path))
    import unittest.mock as m
    with m.patch.object(mw.MPKController, "start", lambda self: False):
        window = MainWindow()

    svg = '<circle cx="32" cy="32" r="14" fill="none" stroke="{accent}" stroke-width="5"/>'
    window._save_normal_binding(
        "pad_1", Binding("pad_1", "trigger", "open_url", {"url": "https://x"}, label="내 링크", icon=svg)
    )

    reloaded = load_config(cfg_path)
    saved = next(b for b in reloaded.banks[reloaded.active_bank].bindings if b.control == "pad_1")
    assert saved.label == "내 링크"
    assert saved.icon == svg
    window.close()


def test_apply_layout_pad_shows_the_layout_name(monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    import mpk_deck.ui.main_window as mw
    from mpk_deck.core.action_registry import Binding
    from mpk_deck.core.layout_store import Layout

    monkeypatch.setattr(mw, "load_layouts", lambda: {"coding": Layout(name="코딩 셋업", items=[])})
    import unittest.mock as m
    with m.patch.object(mw.MPKController, "start", lambda self: False):
        window = MainWindow()
    assert window._layouts == {"coding": Layout(name="코딩 셋업", items=[])}
    window._mini_view.update_bindings(
        {"pad_1": Binding("pad_1", "trigger", "apply_layout", {"layout_id": "coding"})},
        {}, window._layouts,
    )
    assert window._mini_view._pads["pad_1"]._binding_label == "코딩 셋업"
    window.close()
