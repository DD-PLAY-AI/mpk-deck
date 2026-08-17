import mido

from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.midi.mpk_controller import MPKController


def test_find_port_name_matches_substring(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Foo", "MPK mini mk II 1"])
    controller = MPKController(action_engine=ActionEngine())
    assert controller.find_port_name() == "MPK mini mk II 1"


def test_find_port_name_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Foo"])
    controller = MPKController(action_engine=ActionEngine())
    assert controller.find_port_name() is None


def test_on_message_triggers_engine_for_pad():
    engine = ActionEngine()
    calls = []
    engine.trigger = lambda control: calls.append(control)
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("note_on", note=36, velocity=100))

    assert calls == ["pad_1"]


def test_on_message_sets_continuous_for_knob():
    engine = ActionEngine()
    calls = []
    engine.set_continuous = lambda control, value: calls.append((control, value))
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("control_change", control=1, value=64))

    assert calls == [("knob_1", 64 / 127.0)]


def test_on_message_ignores_unmapped_message():
    engine = ActionEngine()
    calls = []
    engine.trigger = lambda control: calls.append(control)
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("note_off", note=36))

    assert calls == []
