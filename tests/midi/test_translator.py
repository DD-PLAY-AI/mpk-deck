import mido
import pytest

from mpk_deck.midi.translator import ControlEvent, is_bank_b_pad_note, translate


def test_translate_pad_note_on_returns_trigger_event():
    msg = mido.Message("note_on", note=36, velocity=100)
    assert translate(msg) == ControlEvent(control="pad_1", kind="trigger")


def test_translate_last_pad_note_maps_to_pad_8():
    msg = mido.Message("note_on", note=43, velocity=100)
    assert translate(msg) == ControlEvent(control="pad_8", kind="trigger")


def test_translate_note_on_zero_velocity_is_ignored():
    msg = mido.Message("note_on", note=36, velocity=0)
    assert translate(msg) is None


def test_translate_keybed_low_c_maps_to_key_0():
    msg = mido.Message("note_on", note=48, velocity=100)
    assert translate(msg) == ControlEvent(control="key_0", kind="trigger")


def test_translate_keybed_middle_note_maps_by_offset():
    msg = mido.Message("note_on", note=60, velocity=100)
    assert translate(msg) == ControlEvent(control="key_12", kind="trigger")


def test_translate_keybed_top_c_maps_to_key_24():
    msg = mido.Message("note_on", note=72, velocity=100)
    assert translate(msg) == ControlEvent(control="key_24", kind="trigger")


def test_translate_note_above_keybed_returns_none():
    msg = mido.Message("note_on", note=73, velocity=100)
    assert translate(msg) is None


def test_translate_bank_b_pad_note_produces_no_control_event():
    # notes 44-47 are Bank B pads; ambiguous vs the keybed, deliberately dropped
    msg = mido.Message("note_on", note=44, velocity=100)
    assert translate(msg) is None


def test_is_bank_b_pad_note_true_for_44_to_47():
    for note in (44, 45, 46, 47):
        assert is_bank_b_pad_note(mido.Message("note_on", note=note, velocity=100)) is True


def test_is_bank_b_pad_note_false_for_zero_velocity():
    assert is_bank_b_pad_note(mido.Message("note_on", note=44, velocity=0)) is False


def test_is_bank_b_pad_note_false_for_note_off():
    assert is_bank_b_pad_note(mido.Message("note_off", note=44, velocity=0)) is False


def test_is_bank_b_pad_note_false_for_bank_a_pad_and_keybed():
    assert is_bank_b_pad_note(mido.Message("note_on", note=43, velocity=100)) is False
    assert is_bank_b_pad_note(mido.Message("note_on", note=48, velocity=100)) is False


def test_is_bank_b_pad_note_false_for_control_change():
    assert is_bank_b_pad_note(mido.Message("control_change", control=1, value=64)) is False


def test_translate_knob_cc_returns_continuous_event_normalized():
    # CC1 now belongs to the joystick's Y axis (see below) - use CC2 (knob_2) here.
    msg = mido.Message("control_change", control=2, value=127)
    event = translate(msg)
    assert event.control == "knob_2"
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


def test_translate_pitchwheel_center_returns_zero():
    msg = mido.Message("pitchwheel", pitch=0)
    assert translate(msg) == ControlEvent(control="joystick_x", kind="continuous", value=0.0)


def test_translate_pitchwheel_positive_extreme_clamps_to_one():
    msg = mido.Message("pitchwheel", pitch=8191)
    event = translate(msg)
    assert event.control == "joystick_x"
    assert event.value == pytest.approx(1.0, abs=0.001)


def test_translate_pitchwheel_negative_extreme_is_exactly_minus_one():
    msg = mido.Message("pitchwheel", pitch=-8192)
    assert translate(msg) == ControlEvent(control="joystick_x", kind="continuous", value=-1.0)


def test_translate_joystick_y_cc_center_returns_zero():
    msg = mido.Message("control_change", control=1, value=64)
    assert translate(msg) == ControlEvent(control="joystick_y", kind="continuous", value=0.0)


def test_translate_joystick_y_cc_max_clamps_to_one():
    msg = mido.Message("control_change", control=1, value=127)
    event = translate(msg)
    assert event.control == "joystick_y"
    assert event.value == pytest.approx(1.0, abs=0.02)


def test_translate_joystick_y_cc_min_is_exactly_minus_one():
    msg = mido.Message("control_change", control=1, value=0)
    assert translate(msg) == ControlEvent(control="joystick_y", kind="continuous", value=-1.0)


def test_translate_joystick_y_cc_takes_priority_over_knob_1():
    """CC1 is also KNOB_CC_TO_CONTROL's entry for knob_1 - joystick_y wins by
    design, see docs/superpowers/specs/2026-08-28-joystick-scroll-design.md."""
    msg = mido.Message("control_change", control=1, value=100)
    event = translate(msg)
    assert event.control == "joystick_y"
