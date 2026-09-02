from dataclasses import dataclass
from typing import Literal, Optional

import mido

# MPK mini MK2 mapping, re-confirmed on hardware 2026-09-02 (this unit's factory
# preset differs from the 2026-08-29 assumptions): pads send notes 32-39 on the
# pad bank the user keeps active, knobs 1-8 were remapped in the AKAI editor to
# CC 2-9 (a +1 shift off the factory CC 1-8) so CC 1 is now the joystick Y axis
# alone - no knob/joystick collision anymore.
PAD_NOTE_TO_CONTROL = {32 + i: f"pad_{i + 1}" for i in range(8)}
KNOB_CC_TO_CONTROL = {cc: f"knob_{cc - 1}" for cc in range(2, 10)}
KEYBED_BASE_NOTE = 48  # C3 - lowest key at the MPK mini MK2's default octave
KEYBED_KEY_COUNT = 25  # 2 octaves + 1, matches the physical keybed and ui/keybed.py NUM_KEYS
BANK_B_PAD_NOTES = frozenset(range(44, 48))  # the other pad bank's low notes, used only for the "switch back" hint

# The joystick Y axis is CC 1. This unit's preset makes it unipolar: value 0 at
# rest, climbing to 127 at full deflection (one direction only), so it decodes to
# [0.0, 1.0], not a bipolar [-1.0, 1.0]. CC 1 no longer carries any knob.
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
            value = max(0.0, min(1.0, message.value / 127))
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
