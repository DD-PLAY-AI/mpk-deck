from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Binding


def test_trigger_calls_registered_handler_with_params():
    engine = ActionEngine()
    calls = []
    engine.register_trigger("launch_program", lambda params: calls.append(params))
    engine.load_bindings([Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "x"})])

    engine.trigger("pad_1")

    assert calls == [{"path": "x"}]


def test_trigger_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.trigger("pad_99")  # no binding loaded at all


def test_trigger_unregistered_action_does_not_raise():
    engine = ActionEngine()
    engine.load_bindings([Binding(control="pad_1", type="trigger", action="nope", params={})])
    engine.trigger("pad_1")


def test_set_continuous_calls_handler_with_value():
    engine = ActionEngine()
    calls = []
    engine.register_continuous("set_system_volume", lambda params, value: calls.append((params, value)))
    engine.load_bindings([Binding(control="knob_1", type="continuous", action="set_system_volume", params={})])

    engine.set_continuous("knob_1", 0.5)

    assert calls == [({}, 0.5)]


def test_set_continuous_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.set_continuous("knob_99", 1.0)
