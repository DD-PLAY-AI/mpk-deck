from dataclasses import dataclass
from typing import Literal, Optional

import mido

# Factory-default MPK mini MK2 mapping: pads on notes 36-43 (Bank A), knobs on CC 1-8.
PAD_NOTE_TO_CONTROL = {36 + i: f"pad_{i + 1}" for i in range(8)}
KNOB_CC_TO_CONTROL = {cc: f"knob_{cc}" for cc in range(2, 9)}
KEYBED_BASE_NOTE = 48  # C3 - lowest key at the MPK mini MK2's default octave
KEYBED_KEY_COUNT = 25  # 2 octaves + 1, matches the physical keybed and ui/keybed.py NUM_KEYS
BANK_B_PAD_NOTES = frozenset(range(44, 48))  # Bank B pads that don't collide with the keybed

# Tentative - unconfirmed on real hardware, see docs/superpowers/specs/
# 2026-08-28-joystick-scroll-design.md "Open questions". Checked before
# KNOB_CC_TO_CONTROL below, so if this really does collide with knob_1's CC on
# the real device, the joystick wins and knob_1 becomes unreachable via CC1
# until a live test resolves it with a one-line constant change.
JOYSTICK_Y_CC = 1


@dataclass(frozen=True)
class ControlEvent:
    control: str
    kind: Literal["trigger", "continuous"]
    value: float = 1.0


def translate(message: mido.Message) -> Optional[ControlEvent]:
    if message.type == "note_on" and message.velocity > 0:
        pad = PAD_NOTE_TO_CONTROL.get(message.note)
        if pad is not None:
            return ControlEvent(control=pad, kind="trigger")
        if KEYBED_BASE_NOTE <= message.note < KEYBED_BASE_NOTE + KEYBED_KEY_COUNT:
            return ControlEvent(control=f"key_{message.note - KEYBED_BASE_NOTE}", kind="trigger")
        return None
    if message.type == "pitchwheel":
        value = max(-1.0, min(1.0, message.pitch / 8192))
        return ControlEvent(control="joystick_x", kind="continuous", value=value)
    if message.type == "control_change":
        if message.control == JOYSTICK_Y_CC:
            value = max(-1.0, min(1.0, (message.value - 64) / 64))
            return ControlEvent(control="joystick_y", kind="continuous", value=value)
        control = KNOB_CC_TO_CONTROL.get(message.control)
        if control is None:
            return None
        return ControlEvent(control=control, kind="continuous", value=message.value / 127.0)
    return None


def is_bank_b_pad_note(message: mido.Message) -> bool:
    """True when `message` is a pad press on the MPK's pad Bank B in a note
    range (44-47) that nothing else on the device sends at the default octave -
    an unambiguous 'pads are on Bank B' signal. Notes 48-51 (also Bank B pads)
    are deliberately excluded because they overlap the keybed."""
    return (
        message.type == "note_on"
        and message.velocity > 0
        and message.note in BANK_B_PAD_NOTES
    )
