from dataclasses import dataclass
from typing import Literal, Optional

import mido

# Factory-default MPK mini MK2 mapping: pads on notes 36-43 (Bank A), knobs on CC 1-8.
PAD_NOTE_TO_CONTROL = {36 + i: f"pad_{i + 1}" for i in range(8)}
KNOB_CC_TO_CONTROL = {1 + i: f"knob_{i + 1}" for i in range(8)}

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
        control = PAD_NOTE_TO_CONTROL.get(message.note, f"key_{message.note}")
        return ControlEvent(control=control, kind="trigger")
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
