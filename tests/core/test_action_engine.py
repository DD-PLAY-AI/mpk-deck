from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Binding


def test_trigger_calls_registered_handler_with_params():
    engine = ActionEngine()
    calls = []
    engine.register_trigger("launch_program", lambda params: calls.append(params))
    engine.load_banks(
        {"bank_a": [Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "x"})]},
        switch_bindings={},
        active_bank="bank_a",
    )

    engine.trigger("pad_1")

    assert calls == [{"path": "x"}]


def test_trigger_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.trigger("pad_99")


def test_trigger_unregistered_action_does_not_raise():
    engine = ActionEngine()
    engine.load_banks(
        {"bank_a": [Binding(control="pad_1", type="trigger", action="nope", params={})]},
        switch_bindings={},
        active_bank="bank_a",
    )
    engine.trigger("pad_1")


def test_set_continuous_calls_handler_with_value():
    engine = ActionEngine()
    calls = []
    engine.register_continuous("set_system_volume", lambda params, value: calls.append((params, value)))
    engine.load_banks(
        {"bank_a": [Binding(control="knob_1", type="continuous", action="set_system_volume", params={})]},
        switch_bindings={},
        active_bank="bank_a",
    )

    engine.set_continuous("knob_1", 0.5)

    assert calls == [({}, 0.5)]


def test_set_continuous_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.set_continuous("knob_99", 1.0)


def test_bindings_reflects_active_bank_only():
    engine = ActionEngine()
    engine.load_banks(
        {
            "bank_a": [Binding(control="pad_1", type="trigger", action="a", params={})],
            "bank_b": [Binding(control="pad_1", type="trigger", action="b", params={})],
        },
        switch_bindings={},
        active_bank="bank_a",
    )
    assert engine.bindings["pad_1"].action == "a"


def test_switch_bindings_always_present_regardless_of_active_bank():
    engine = ActionEngine()
    engine.load_banks({"bank_a": [], "bank_b": []}, switch_bindings={"key_0": "bank_a"}, active_bank="bank_b")
    binding = engine.bindings["key_0"]
    assert binding.action == "switch_bank"
    assert binding.params == {"bank_id": "bank_a"}


def test_trigger_on_switch_control_switches_active_bank():
    engine = ActionEngine()
    engine.load_banks(
        {
            "bank_a": [Binding(control="pad_1", type="trigger", action="a", params={})],
            "bank_b": [Binding(control="pad_1", type="trigger", action="b", params={})],
        },
        switch_bindings={"key_0": "bank_b"},
        active_bank="bank_a",
    )

    engine.trigger("key_0")

    assert engine.active_bank == "bank_b"
    assert engine.bindings["pad_1"].action == "b"


def test_switch_bank_calls_on_bank_changed_callback():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": [], "bank_b": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("bank_b")

    assert calls == ["bank_b"]


def test_switch_bank_to_same_bank_is_a_noop():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("bank_a")

    assert calls == []


def test_switch_binding_overrides_bank_binding_on_same_control():
    engine = ActionEngine()
    engine.load_banks(
        {
            "bank_a": [Binding(control="key_0", type="trigger", action="a", params={})],
            "bank_b": [],
        },
        switch_bindings={"key_0": "bank_b"},
        active_bank="bank_a",
    )
    binding = engine.bindings["key_0"]
    assert binding.action == "switch_bank"
    assert binding.params == {"bank_id": "bank_b"}


def test_switch_bank_to_unknown_bank_is_ignored():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("does_not_exist")

    assert engine.active_bank == "bank_a"
    assert calls == []


def test_set_continuous_calls_on_continuous_callback_for_any_control():
    calls = []
    engine = ActionEngine(on_continuous=lambda c, v: calls.append((c, v)))

    engine.set_continuous("joystick_x", 0.5)

    assert calls == [("joystick_x", 0.5)]


def test_set_continuous_calls_on_continuous_even_when_handler_is_registered():
    calls = []
    engine = ActionEngine(on_continuous=lambda c, v: calls.append((c, v)))
    engine.register_continuous("scroll_horizontal", lambda params, value: None)
    engine.load_banks(
        {"bank_a": [Binding(control="joystick_x", type="continuous", action="scroll_horizontal", params={})]},
        switch_bindings={},
        active_bank="bank_a",
    )

    engine.set_continuous("joystick_x", 0.7)

    assert calls == [("joystick_x", 0.7)]


def test_set_continuous_without_on_continuous_callback_does_not_raise():
    engine = ActionEngine()
    engine.set_continuous("joystick_x", 0.5)
