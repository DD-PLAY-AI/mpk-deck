import mido

from mpk_deck.midi.translator import ControlEvent, translate


def test_translate_pad_note_on_returns_trigger_event():
    msg = mido.Message("note_on", note=36, velocity=100)
    assert translate(msg) == ControlEvent(control="pad_1", kind="trigger")


def test_translate_last_pad_note_maps_to_pad_8():
    msg = mido.Message("note_on", note=43, velocity=100)
    assert translate(msg) == ControlEvent(control="pad_8", kind="trigger")


def test_translate_note_on_zero_velocity_is_ignored():
    msg = mido.Message("note_on", note=36, velocity=0)
    assert translate(msg) is None


def test_translate_unmapped_note_falls_back_to_key_control():
    msg = mido.Message("note_on", note=60, velocity=100)
    assert translate(msg) == ControlEvent(control="key_60", kind="trigger")


def test_translate_knob_cc_returns_continuous_event_normalized():
    msg = mido.Message("control_change", control=1, value=127)
    event = translate(msg)
    assert event.control == "knob_1"
    assert event.kind == "continuous"
    assert event.value == 1.0


def test_translate_knob_cc_zero_value_normalizes_to_zero():
    msg = mido.Message("control_change", control=8, value=0)
    event = translate(msg)
    assert event.control == "knob_8"
    assert event.value == 0.0


def test_translate_unmapped_cc_returns_none():
    msg = mido.Message("control_change", control=99, value=10)
    assert translate(msg) is None


def test_translate_note_off_returns_none():
    msg = mido.Message("note_off", note=36)
    assert translate(msg) is None
