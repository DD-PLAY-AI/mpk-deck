from dataclasses import dataclass
from typing import Literal, Optional

import mido

# Factory-default MPK mini MK2 mapping: pads on notes 36-43 (Bank A), knobs on CC 1-8.
PAD_NOTE_TO_CONTROL = {36 + i: f"pad_{i + 1}" for i in range(8)}
KNOB_CC_TO_CONTROL = {1 + i: f"knob_{i + 1}" for i in range(8)}


@dataclass(frozen=True)
class ControlEvent:
    control: str
    kind: Literal["trigger", "continuous"]
    value: float = 1.0


def translate(message: mido.Message) -> Optional[ControlEvent]:
    if message.type == "note_on" and message.velocity > 0:
        control = PAD_NOTE_TO_CONTROL.get(message.note, f"key_{message.note}")
        return ControlEvent(control=control, kind="trigger")
    if message.type == "control_change":
        control = KNOB_CC_TO_CONTROL.get(message.control)
        if control is None:
            return None
        return ControlEvent(control=control, kind="continuous", value=message.value / 127.0)
    return None
