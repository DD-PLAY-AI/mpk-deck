# Sub-project F — Hardware Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire every MIDI-capable MPK mini MK2 control (pads, keys, knobs 2–8, joystick) end-to-end into the deck using the factory MIDI mapping, make the MIDI-silent function buttons visibly inert, and show pass/fail feedback on every triggered action.

**Architecture:** `midi/translator.py` gains a real keybed note range (48–72 → `key_0`–`key_24`) and a Bank-B pad detector. `core/action_engine.py` gains an `on_trigger(control, ok)` callback that reports whether a handler ran cleanly. `midi/mpk_controller.py` forwards the Bank-B signal. The UI (`ui/expanded_view.py`, `ui/mini_view.py`, `ui/main_window.py`) mutes the 10 function buttons, mirrors the joystick-Y value into the knob-1 dial, flashes pads/keys green/red on trigger, and shows a transient "switch to Bank A" banner.

**Tech Stack:** Python 3.13, PySide6, `mido` + `python-rtmidi`, pytest. Pure logic is pytest-covered; Qt widgets are verified with off-screen (`QT_QPA_PLATFORM=offscreen`) smoke scripts plus user live verification (project policy in `CLAUDE.md`).

**Spec:** `docs/superpowers/specs/2026-08-29-hardware-wiring-design.md`

## Global Constraints

- Python >= 3.13; package manager is plain `pip` (`pip install -e ".[dev]"`). No new dependencies.
- Hardware-specific imports (`win32*`, `pycaw`, `rtmidi`) stay lazily imported inside functions; modules must import without the hardware/OS present.
- Event-driven MIDI only — no polling loops (`mido` callbacks).
- Desktop UI stays lightweight — no busy-wait; reuse one `QTimer` per widget for flashes, never one per event.
- Tests mirror `src/` layout under `tests/` (e.g. `midi/translator.py` ↔ `tests/midi/test_translator.py`). New pure logic must be pytest-covered; extract pure functions rather than testing Qt widgets.
- Qt widget behaviour (`ui/*_view.py`, `ui/main_window.py`) is not pytest-covered — verify with off-screen smoke scripts and hand to the user for live checks.
- Full suite must stay green (`pytest`); currently 165 tests pass on `main` at `db8b8d1`.
- Commit per task with Conventional Commits; do not push (user pushes).
- Never bind actions to, or route MIDI through, the function buttons — they transmit nothing.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/mpk_deck/midi/translator.py` | pure MIDI message → `ControlEvent` | keybed range mapping, drop out-of-range notes, clean knob-1 entry, add `is_bank_b_pad_note()` |
| `src/mpk_deck/core/action_engine.py` | action dispatch | add `on_trigger` callback + exception capture in `trigger()` |
| `src/mpk_deck/midi/mpk_controller.py` | MIDI port lifecycle + message fan-out | add `on_bank_b_pad` kwarg, call `is_bank_b_pad_note` in `_on_message` |
| `src/mpk_deck/ui/expanded_view.py` | ExpandedView widgets | mute function buttons + "can't configure" signal; knob double-click (config for 2–8, block message for knob_1); `flash_control()` |
| `src/mpk_deck/ui/mini_view.py` | MiniView pads | `flash_control()`; `PadButton.flash()` |
| `src/mpk_deck/ui/bank_hint.py` (new) | transient "switch to Bank A" overlay label | new small widget, same pattern as `ui/bank_indicator.py` |
| `src/mpk_deck/ui/main_window.py` | integration point | wire `on_trigger` + `on_bank_b_pad`, marshal to Qt thread, flash dispatch, knob-1 mirror, decorative/knob messages, banner |
| `tests/midi/test_translator.py` | translator tests | update `key_60` expectation, add keybed-range + `is_bank_b_pad_note` tests |
| `tests/core/test_action_engine.py` | engine tests | add `on_trigger` tests |
| `tests/midi/test_mpk_controller.py` | controller tests | add `on_bank_b_pad` fan-out tests |
| `ROADMAP.md`, `src/mpk_deck/CLAUDE.md` | project docs | mark F done; list deferred items as future rounds |

---

## Task 1: translator — real keybed range + Bank-B detector

**Files:**
- Modify: `src/mpk_deck/midi/translator.py`
- Test: `tests/midi/test_translator.py`

**Interfaces:**
- Consumes: `mido.Message`, existing `ControlEvent` dataclass, `PAD_NOTE_TO_CONTROL` (notes 36–43 → `pad_1`..`pad_8`).
- Produces:
  - `KEYBED_BASE_NOTE: int = 48`, `KEYBED_KEY_COUNT: int = 25` (module constants).
  - `translate(message) -> Optional[ControlEvent]` — unchanged signature; keybed notes now map `note - 48` into `key_0`..`key_24`, notes outside the pad range and the keybed range yield `None`.
  - `is_bank_b_pad_note(message: mido.Message) -> bool` — `True` only for a `note_on` with `velocity > 0` and `note` in 44..47 inclusive.

- [ ] **Step 1: Update the stale fallthrough test and add the new expectations**

In `tests/midi/test_translator.py`, replace `test_translate_unmapped_note_falls_back_to_key_control` with:

```python
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
```

Add, in the same file:

```python
from mpk_deck.midi.translator import is_bank_b_pad_note  # add to the existing import line


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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/midi/test_translator.py -q`
Expected: FAIL — `test_translate_keybed_middle_note_maps_by_offset` gets `key_60`, the `is_bank_b_pad_note` import fails (`ImportError`), `test_translate_note_above_keybed_returns_none` gets `key_73`.

- [ ] **Step 3: Implement the keybed range and the detector**

In `src/mpk_deck/midi/translator.py`:

Add constants near the top, after `KNOB_CC_TO_CONTROL`:

```python
KEYBED_BASE_NOTE = 48  # C3 - lowest key at the MPK mini MK2's default octave
KEYBED_KEY_COUNT = 25  # 2 octaves + 1, matches the physical keybed and ui/keybed.py NUM_KEYS
BANK_B_PAD_NOTES = frozenset(range(44, 48))  # Bank B pads that don't collide with the keybed
```

Change `KNOB_CC_TO_CONTROL` so it no longer contains the dead CC1 entry (CC1 is intercepted as `joystick_y`):

```python
KNOB_CC_TO_CONTROL = {cc: f"knob_{cc}" for cc in range(2, 9)}
```

Replace the `note_on` branch of `translate()`:

```python
    if message.type == "note_on" and message.velocity > 0:
        pad = PAD_NOTE_TO_CONTROL.get(message.note)
        if pad is not None:
            return ControlEvent(control=pad, kind="trigger")
        if KEYBED_BASE_NOTE <= message.note < KEYBED_BASE_NOTE + KEYBED_KEY_COUNT:
            return ControlEvent(control=f"key_{message.note - KEYBED_BASE_NOTE}", kind="trigger")
        return None
```

Add the detector as a top-level function:

```python
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
```

- [ ] **Step 4: Run the translator tests**

Run: `pytest tests/midi/test_translator.py -q`
Expected: PASS (all, including the unchanged joystick/knob/pitchwheel tests).

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS. If `tests/midi/test_mpk_controller.py::test_on_message_triggers_engine_for_pad` or similar references note 60 as a key, it still passes (note 60 → `key_12` is still a trigger event; only the control id changed, and that test asserts note 36 → `pad_1`).

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/midi/translator.py tests/midi/test_translator.py
git commit -m "feat(midi): map keybed notes 48-72 to key_0-24, add Bank B pad detector"
```

---

## Task 2: ActionEngine — on_trigger pass/fail callback

**Files:**
- Modify: `src/mpk_deck/core/action_engine.py`
- Test: `tests/core/test_action_engine.py`

**Interfaces:**
- Consumes: existing `ActionEngine.__init__`, `register_trigger`, `trigger`, `switch_bank`.
- Produces:
  - `ActionEngine.__init__` gains `on_trigger: Optional[Callable[[str, bool], None]] = None` (keyword-only in effect — appended after `on_continuous`).
  - `trigger(control)` still returns `None`. When a registered handler runs: catch `Exception`, log it (`logger.warning("trigger handler for %s failed", binding.action, exc_info=True)`), then call `on_trigger(control, False)`; on clean return call `on_trigger(control, True)`. A `switch_bank` dispatch calls `on_trigger(control, True)`. When there is no binding or no handler, `on_trigger` is **not** called.

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_action_engine.py`:

```python
def test_on_trigger_reports_success_for_clean_handler():
    calls = []
    engine = ActionEngine(on_trigger=lambda control, ok: calls.append((control, ok)))
    engine.register_trigger("noop", lambda params: None)
    engine.load_banks({"b": [Binding(control="pad_1", type="trigger", action="noop", params={})]}, {}, "b")

    engine.trigger("pad_1")

    assert calls == [("pad_1", True)]


def test_on_trigger_reports_failure_when_handler_raises(caplog):
    calls = []
    engine = ActionEngine(on_trigger=lambda control, ok: calls.append((control, ok)))

    def boom(params):
        raise RuntimeError("handler blew up")

    engine.register_trigger("boom", boom)
    engine.load_banks({"b": [Binding(control="pad_1", type="trigger", action="boom", params={})]}, {}, "b")

    engine.trigger("pad_1")  # must not raise

    assert calls == [("pad_1", False)]
    assert "failed" in caplog.text


def test_on_trigger_not_called_when_control_is_unbound():
    calls = []
    engine = ActionEngine(on_trigger=lambda control, ok: calls.append((control, ok)))
    engine.load_banks({"b": []}, {}, "b")

    engine.trigger("pad_1")

    assert calls == []


def test_on_trigger_not_called_when_no_handler_registered():
    calls = []
    engine = ActionEngine(on_trigger=lambda control, ok: calls.append((control, ok)))
    engine.load_banks({"b": [Binding(control="pad_1", type="trigger", action="ghost", params={})]}, {}, "b")

    engine.trigger("pad_1")

    assert calls == []


def test_on_trigger_reports_success_for_switch_bank():
    calls = []
    engine = ActionEngine(on_trigger=lambda control, ok: calls.append((control, ok)))
    engine.load_banks({"home": [], "work": []}, {"pad_1": "work"}, "home")

    engine.trigger("pad_1")

    assert calls == [("pad_1", True)]
    assert engine.active_bank == "work"
```

(Confirm `Binding` is already imported in this test file; the bank tests use it.)

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/core/test_action_engine.py -q -k on_trigger`
Expected: FAIL — `ActionEngine.__init__() got an unexpected keyword argument 'on_trigger'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/core/action_engine.py`:

`__init__` signature and body:

```python
    def __init__(
        self,
        on_bank_changed: Optional[Callable[[str], None]] = None,
        on_continuous: Optional[Callable[[str, float], None]] = None,
        on_trigger: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        ...
        self._on_continuous = on_continuous
        self._on_trigger = on_trigger
```

`trigger()`:

```python
    def trigger(self, control: str) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            logger.info("no binding for control %s", control)
            return
        if binding.action == "switch_bank":
            self.switch_bank(binding.params["bank_id"])
            self._report_trigger(control, True)
            return
        handler = self._trigger_handlers.get(binding.action)
        if handler is None:
            logger.warning("no trigger handler registered for action %s", binding.action)
            return
        try:
            handler(binding.params)
        except Exception:
            logger.warning("trigger handler for %s failed", binding.action, exc_info=True)
            self._report_trigger(control, False)
            return
        self._report_trigger(control, True)

    def _report_trigger(self, control: str, ok: bool) -> None:
        if self._on_trigger is not None:
            self._on_trigger(control, ok)
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/core/test_action_engine.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/core/action_engine.py tests/core/test_action_engine.py
git commit -m "feat(engine): add on_trigger(control, ok) pass/fail callback"
```

---

## Task 3: MPKController — forward the Bank-B pad signal

**Files:**
- Modify: `src/mpk_deck/midi/mpk_controller.py`
- Test: `tests/midi/test_mpk_controller.py`

**Interfaces:**
- Consumes: `translate`, and now `is_bank_b_pad_note` from `mpk_deck.midi.translator` (Task 1).
- Produces:
  - `MPKController.__init__(self, action_engine, port_name_contains="MPK mini", on_bank_b_pad: Optional[Callable[[], None]] = None)`.
  - `_on_message` calls `is_bank_b_pad_note(message)` and, when true, calls `self._on_bank_b_pad()` if set. Existing translate/trigger/set_continuous behaviour and the try/except wrapper are unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/midi/test_mpk_controller.py`:

```python
def test_on_message_fires_bank_b_pad_callback_for_note_44():
    calls = []
    controller = MPKController(action_engine=ActionEngine(), on_bank_b_pad=lambda: calls.append(True))

    controller._on_message(mido.Message("note_on", note=44, velocity=100))

    assert calls == [True]


def test_on_message_does_not_fire_bank_b_pad_callback_for_keybed_note():
    calls = []
    controller = MPKController(action_engine=ActionEngine(), on_bank_b_pad=lambda: calls.append(True))

    controller._on_message(mido.Message("note_on", note=48, velocity=100))

    assert calls == []


def test_on_message_without_bank_b_callback_does_not_raise():
    controller = MPKController(action_engine=ActionEngine())
    controller._on_message(mido.Message("note_on", note=44, velocity=100))  # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/midi/test_mpk_controller.py -q -k bank_b`
Expected: FAIL — `__init__() got an unexpected keyword argument 'on_bank_b_pad'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/midi/mpk_controller.py`:

```python
from mpk_deck.midi.translator import is_bank_b_pad_note, translate
```

```python
    def __init__(
        self,
        action_engine: ActionEngine,
        port_name_contains: str = "MPK mini",
        on_bank_b_pad: Optional[Callable[[], None]] = None,
    ) -> None:
        self._engine = action_engine
        self._port_name_contains = port_name_contains
        self._on_bank_b_pad = on_bank_b_pad
        self._port = None
```

Add `from typing import Callable, Optional` at the top if not already present.

In `_on_message`, inside the existing `try`:

```python
    def _on_message(self, message: mido.Message) -> None:
        try:
            if self._on_bank_b_pad is not None and is_bank_b_pad_note(message):
                self._on_bank_b_pad()
            event = translate(message)
            if event is None:
                return
            if event.kind == "trigger":
                self._engine.trigger(event.control)
            else:
                self._engine.set_continuous(event.control, event.value)
        except Exception:
            logger.warning("error handling MIDI input callback", exc_info=True)
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/midi/test_mpk_controller.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/midi/mpk_controller.py tests/midi/test_mpk_controller.py
git commit -m "feat(midi): forward Bank B pad detection via on_bank_b_pad callback"
```

---

## Task 4: ExpandedView — mute the 10 function buttons

**Files:**
- Modify: `src/mpk_deck/ui/expanded_view.py`
- Verify: off-screen smoke script (throwaway, in `scratchpad/`)

**Interfaces:**
- Consumes: `LEFT_BUTTONS`, `RIGHT_BUTTONS`, `PadButton`, existing `control_activated` / `control_configure_requested` signals.
- Produces:
  - New signal `ExpandedView.decorative_button_activated = Signal(str)` — emitted (with the control id) when the user double-clicks any function button.
  - The 10 function buttons (`arp_on_off`, `tap_tempo`, `octave_down`, `octave_up`, `full_level`, `note_repeat`, `bank_ab`, `cc`, `prog_change`, `prog_select`) no longer emit `control_activated` / `control_configure_requested`; they render at reduced opacity.

- [ ] **Step 1: Write the off-screen smoke script**

Create `scratchpad/f_task4_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent
from mpk_deck.ui.expanded_view import ExpandedView, LEFT_BUTTONS, RIGHT_BUTTONS

app = QApplication([])
view = ExpandedView()
view.resize(700, 420)

activated, configured, decorative = [], [], []
view.control_activated.connect(activated.append)
view.control_configure_requested.connect(configured.append)
view.decorative_button_activated.connect(decorative.append)

btn = view._buttons["arp_on_off"]
# simulate a double-click on the function button
pos = btn.rect().center()
for etype in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease):
    app.sendEvent(btn, QMouseEvent(etype, pos, btn.mapToGlobal(pos),
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

app.processEvents()
print("activated:", activated)
print("configured:", configured)
print("decorative:", decorative)
assert activated == [] and configured == [], "function button must not drive actions"
assert decorative == ["arp_on_off"], f"expected decorative signal, got {decorative}"
# opacity check: function buttons dimmer than pads
print("btn windowOpacity/style set:", btn.styleSheet()[:60])
print("OK")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python scratchpad/f_task4_smoke.py`
Expected: FAIL — `AttributeError: 'ExpandedView' object has no attribute 'decorative_button_activated'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/ui/expanded_view.py`:

Add a module constant next to `GROUPED_RIGHT_BUTTONS`:

```python
DECORATIVE_CONTROLS = frozenset(
    c for c, _text, _tip in LEFT_BUTTONS + RIGHT_BUTTONS
)  # every MPK function button - none of them transmit MIDI
```

Add the signal to `ExpandedView`:

```python
class ExpandedView(WindowGripMixin, QWidget):
    control_activated = Signal(str)
    control_configure_requested = Signal(str)
    decorative_button_activated = Signal(str)
```

In `__init__`, change the button-creation loop:

```python
        self._buttons: dict[str, PadButton] = {}
        for control, text, tooltip in LEFT_BUTTONS + RIGHT_BUTTONS:
            btn = PadButton(text, self)
            btn.setToolTip(tooltip)
            # function buttons send no MIDI - decorative only, no action wiring
            btn.configure_requested.connect(lambda c=control: self.decorative_button_activated.emit(c))
            self._buttons[control] = btn
```

In `_layout_controls`, after the existing `btn_qss` loop, dim the decorative buttons. Replace:

```python
        btn_qss = _button_qss(colors, btn_font, radius=4 * scale, accent_hex=self._accent_hex)
        for control, btn in self._buttons.items():
            btn.setStyleSheet(btn_qss)
            btn.setFixedSize(btn_w, btn_h)
```

with:

```python
        btn_qss = _button_qss(colors, btn_font, radius=4 * scale, accent_hex=self._accent_hex)
        muted_qss = btn_qss + " QPushButton { color: rgba(150,150,160,150); }"
        for control, btn in self._buttons.items():
            btn.setStyleSheet(muted_qss if control in DECORATIVE_CONTROLS else btn_qss)
            btn.setFixedSize(btn_w, btn_h)
```

(All 10 are in `DECORATIVE_CONTROLS`, so every entry uses `muted_qss`; the branch keeps the code honest if a future button becomes real.)

- [ ] **Step 4: Run the smoke script**

Run: `python scratchpad/f_task4_smoke.py`
Expected: prints `decorative: ['arp_on_off']`, `activated: []`, `configured: []`, then `OK`.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS (no pytest touches these Qt widgets).

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/ui/expanded_view.py
git commit -m "feat(ui): make MPK function buttons decorative-only in ExpandedView"
```

---

## Task 5: KnobWidget — double-click config for 2–8, block message for knob_1

**Files:**
- Modify: `src/mpk_deck/ui/expanded_view.py`
- Verify: off-screen smoke script

**Interfaces:**
- Consumes: `KnobWidget`, `ExpandedView._knobs` dict, `ExpandedView.control_configure_requested`.
- Produces:
  - `KnobWidget.configure_requested = Signal()` and `KnobWidget.blocked_configure_requested = Signal()`.
  - `KnobWidget.mouseDoubleClickEvent` emits one of them.
  - `ExpandedView` connects knob 2–8's `configure_requested` → `control_configure_requested.emit("knob_N")`, and `knob_1`'s `blocked_configure_requested` → a new `ExpandedView.knob_locked_activated = Signal()`.

- [ ] **Step 1: Write the off-screen smoke script**

Create `scratchpad/f_task5_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QMouseEvent
from mpk_deck.ui.expanded_view import ExpandedView

app = QApplication([])
view = ExpandedView()
view.resize(700, 420)
configured, locked = [], []
view.control_configure_requested.connect(configured.append)
view.knob_locked_activated.connect(lambda: locked.append(True))

def dbl(widget):
    pos = widget.rect().center()
    for etype in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease):
        app.sendEvent(widget, QMouseEvent(etype, pos, widget.mapToGlobal(pos),
                      Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    app.processEvents()

dbl(view._knobs["knob_3"])
dbl(view._knobs["knob_1"])
print("configured:", configured, "locked:", locked)
assert configured == ["knob_3"], configured
assert locked == [True], locked
print("OK")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python scratchpad/f_task5_smoke.py`
Expected: FAIL — `AttributeError: 'ExpandedView' object has no attribute 'knob_locked_activated'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/ui/expanded_view.py`, `KnobWidget`:

```python
class KnobWidget(QFrame):
    configure_requested = Signal()
    blocked_configure_requested = Signal()

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label = label
        self._value = 0.0
        self._style = "B"
        self._colors = _DARK
        self._accent_hex = ACCENT_HEX
        self._locked = label == "1"  # knob 1 shares CC1 with the joystick Y axis

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._locked:
            self.blocked_configure_requested.emit()
        else:
            self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)
```

(`KnobWidget` is constructed as `KnobWidget(control.split("_")[1].upper(), self)` so its label is `"1"`..`"8"`; `self._locked` keys off `"1"`.)

Add the signal to `ExpandedView`:

```python
    decorative_button_activated = Signal(str)
    knob_locked_activated = Signal()
```

In `ExpandedView.__init__`, change the knob-creation loop:

```python
        self._knobs: dict[str, KnobWidget] = {}
        for control in KNOB_LABELS_TOP + KNOB_LABELS_BOTTOM:
            knob = KnobWidget(control.split("_")[1].upper(), self)
            knob.configure_requested.connect(lambda c=control: self.control_configure_requested.emit(c))
            knob.blocked_configure_requested.connect(self.knob_locked_activated.emit)
            self._knobs[control] = knob
```

- [ ] **Step 4: Run the smoke script**

Run: `python scratchpad/f_task5_smoke.py`
Expected: prints `configured: ['knob_3'] locked: [True]`, then `OK`.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/ui/expanded_view.py
git commit -m "feat(ui): knob double-click configures knobs 2-8, blocks knob 1"
```

---

## Task 6: Trigger flash on pads and keys

**Files:**
- Modify: `src/mpk_deck/ui/mini_view.py`, `src/mpk_deck/ui/expanded_view.py`
- Verify: off-screen smoke script

**Interfaces:**
- Consumes: `PadButton` (has `_glow: QGraphicsDropShadowEffect`), `_DebouncedKey` (QFrame, no glow yet), `MiniView._pads`, `ExpandedView._pads`, `ExpandedView._keys`.
- Produces:
  - `PadButton.flash(ok: bool)` — green glow for `ok=True`, red for `ok=False`, ~200 ms then off. Reuses the existing `_glow` effect and one reused `QTimer`.
  - `_DebouncedKey.flash(ok: bool)` — same behaviour; add a `QGraphicsDropShadowEffect` + reused `QTimer` to `_DebouncedKey`.
  - `MiniView.flash_control(control: str, ok: bool)` — flashes `self._pads[control]` if present, else no-op.
  - `ExpandedView.flash_control(control: str, ok: bool)` — flashes `self._pads[control]` or `self._keys[int(control[4:])]` (for `key_N`) if present, else no-op.

- [ ] **Step 1: Write the off-screen smoke script**

Create `scratchpad/f_task6_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from mpk_deck.ui.mini_view import MiniView
from mpk_deck.ui.expanded_view import ExpandedView

app = QApplication([])

mini = MiniView()
mini.flash_control("pad_1", True)
assert mini._pads["pad_1"]._glow.isEnabled()
assert mini._pads["pad_1"]._glow.color().green() > 150
mini.flash_control("pad_2", False)
assert mini._pads["pad_2"]._glow.color().red() > 150
mini.flash_control("nonexistent", True)  # no-op, must not raise

exp = ExpandedView()
exp.flash_control("pad_3", True)
assert exp._pads["pad_3"]._glow.isEnabled()
exp.flash_control("key_0", False)
assert exp._keys[0]._glow.isEnabled()
assert exp._keys[0]._glow.color().red() > 150
exp.flash_control("key_99", True)  # no-op, must not raise
print("OK")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python scratchpad/f_task6_smoke.py`
Expected: FAIL — `AttributeError: 'MiniView' object has no attribute 'flash_control'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/ui/mini_view.py`, add to `PadButton`:

```python
    def __init__(self, text: str, parent=None) -> None:
        ...
        self.setGraphicsEffect(self._glow)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self._glow.setEnabled(False))

    def flash(self, ok: bool) -> None:
        self._glow.setColor(QColor(0, 200, 90) if ok else QColor(220, 60, 60))
        self._glow.setEnabled(True)
        self._flash_timer.start(200)
```

(Import `QColor` is already imported in `mini_view.py`. After the flash the next press restores the accent colour via `set_accent`/`_on_clicked`; also reset the colour at the start of `mousePressEvent`'s glow-enable so a manual press after a flash isn't tinted — add `self._glow.setColor(QColor(self._accent_hex))` in `mousePressEvent` before `setEnabled(True)`.)

Add to `MiniView`:

```python
    def flash_control(self, control: str, ok: bool) -> None:
        pad = self._pads.get(control)
        if pad is not None:
            pad.flash(ok)
```

In `src/mpk_deck/ui/expanded_view.py`, add a glow + flash to `_DebouncedKey`:

```python
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(16)
        self._glow.setOffset(0, 0)
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self._glow.setEnabled(False))

    def flash(self, ok: bool) -> None:
        self._glow.setColor(QColor(0, 200, 90) if ok else QColor(220, 60, 60))
        self._glow.setEnabled(True)
        self._flash_timer.start(200)
```

Add imports to `expanded_view.py`: `QGraphicsDropShadowEffect` from `PySide6.QtWidgets`, `QColor` is already imported.

Add to `ExpandedView`:

```python
    def flash_control(self, control: str, ok: bool) -> None:
        pad = self._pads.get(control)
        if pad is not None:
            pad.flash(ok)
            return
        if control.startswith("key_"):
            key = self._keys.get(int(control[4:]))
            if key is not None:
                key.flash(ok)
```

- [ ] **Step 4: Run the smoke script**

Run: `python scratchpad/f_task6_smoke.py`
Expected: `OK`.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/ui/mini_view.py src/mpk_deck/ui/expanded_view.py
git commit -m "feat(ui): green/red trigger flash on pads and keys"
```

---

## Task 7: Bank-B hint banner widget

**Files:**
- Create: `src/mpk_deck/ui/bank_hint.py`
- Verify: off-screen smoke script

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone widget). Mirrors the style of `src/mpk_deck/ui/bank_indicator.py` (read it first for the opaque-badge pattern and `set_accent`).
- Produces:
  - `class BankHint(QWidget)` — a `MainWindow`-child overlay label reading `"패드가 Bank B로 설정되어 있습니다 — 기기의 BANK 버튼으로 Bank A로 전환하세요."`.
  - `BankHint.show_hint()` — makes it visible and (re)starts a ~4000 ms single-shot `QTimer` that hides it.
  - `BankHint.set_accent(accent_hex: str)` — restyles (accent background, readable text), matching `BankIndicator`.
  - Starts hidden.

- [ ] **Step 1: Write the off-screen smoke script**

Create `scratchpad/f_task7_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget
from mpk_deck.ui.bank_hint import BankHint

app = QApplication([])
host = QWidget()
hint = BankHint(host)
assert not hint.isVisible()
hint.set_accent("#3a6df0")
hint.show_hint()
assert hint.isVisible()
assert hint._hide_timer.isActive()
hint.show_hint()  # re-arm, must not raise
print("text:", hint.text() if hasattr(hint, "text") else hint._label.text())
print("OK")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python scratchpad/f_task7_smoke.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpk_deck.ui.bank_hint'`.

- [ ] **Step 3: Implement**

First read `src/mpk_deck/ui/bank_indicator.py` to match its structure. Then create `src/mpk_deck/ui/bank_hint.py`:

```python
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel

from mpk_deck.config import ACCENT_HEX
from mpk_deck.ui.accent import hex_to_rgb_str

HINT_TEXT = "패드가 Bank B로 설정되어 있습니다 - 기기의 BANK 버튼으로 Bank A로 전환하세요."
VISIBLE_MS = 4000


class BankHint(QLabel):
    """Transient overlay shown when the MPK sends a Bank B pad note (44-47).
    Same MainWindow-child overlay pattern as BankIndicator; auto-hides."""

    def __init__(self, parent=None) -> None:
        super().__init__(HINT_TEXT, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWordWrap(False)
        self._accent_hex = ACCENT_HEX
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.set_accent(ACCENT_HEX)
        self.hide()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        rgb = hex_to_rgb_str(accent_hex)
        self.setStyleSheet(
            f"QLabel {{ background: rgba({rgb},235); color: #ffffff; "
            f"border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 600; }}"
        )
        self.adjustSize()

    def show_hint(self) -> None:
        self.adjustSize()
        self.show()
        self.raise_()
        self._hide_timer.start(VISIBLE_MS)
```

- [ ] **Step 4: Run the smoke script**

Run: `python scratchpad/f_task7_smoke.py`
Expected: prints the text, `OK`. (The `hint._label.text()` fallback in the script won't be hit — `BankHint` is a `QLabel` so `hint.text()` works; adjust the script's print line to just `hint.text()` if you prefer.)

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/ui/bank_hint.py
git commit -m "feat(ui): add transient Bank B -> Bank A hint banner"
```

---

## Task 8: MainWindow — wire it all together

**Files:**
- Modify: `src/mpk_deck/ui/main_window.py`
- Verify: off-screen smoke script + full `pytest`

**Interfaces:**
- Consumes:
  - `ActionEngine(on_trigger=...)` (Task 2), `MPKController(on_bank_b_pad=...)` (Task 3).
  - `MiniView.flash_control(control, ok)`, `ExpandedView.flash_control(control, ok)` (Task 6).
  - `ExpandedView.decorative_button_activated: Signal(str)`, `ExpandedView.knob_locked_activated: Signal()` (Tasks 4–5).
  - `BankHint` (Task 7), `ExpandedView.set_knob_value(control, value)` (existing).
- Produces: fully wired hardware feedback. No new public API on `MainWindow`.

- [ ] **Step 1: Write the off-screen smoke script**

Create `scratchpad/f_task8_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from mpk_deck.ui.main_window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
for _ in range(5):
    app.processEvents()

# 1. joystick_y value mirrors into the knob_1 dial (remapped -1..1 -> 0..1)
w._on_joystick_continuous("joystick_y", 1.0)
for _ in range(3):
    app.processEvents()
assert abs(w._expanded_view._knobs["knob_1"]._value - 1.0) < 0.01, w._expanded_view._knobs["knob_1"]._value
w._on_joystick_continuous("joystick_y", -1.0)
for _ in range(3):
    app.processEvents()
assert abs(w._expanded_view._knobs["knob_1"]._value - 0.0) < 0.01

# 2. on_trigger flashes the pad in the visible view
w._mode = "mini"
w._apply_mode()
w._on_trigger("pad_1", True)
for _ in range(3):
    app.processEvents()
assert w._mini_view._pads["pad_1"]._glow.isEnabled()

# 3. bank B pad -> banner shows
w._on_bank_b_pad()
for _ in range(3):
    app.processEvents()
assert w._bank_hint.isVisible()

# 4. decorative button + locked knob -> no crash (message boxes are suppressed offscreen;
#    just confirm the slots exist and run)
w._on_decorative_button("arp_on_off")
w._on_knob_locked()
print("OK")
```

(Note: `QMessageBox.information` on the offscreen platform returns immediately without blocking. If it does block in CI, wrap the two message calls in the smoke with a `QTimer.singleShot(0, ...)` dismiss, or guard them behind a check — but offscreen normally does not block.)

- [ ] **Step 2: Run it to see it fail**

Run: `python scratchpad/f_task8_smoke.py`
Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute '_on_trigger'`.

- [ ] **Step 3: Implement**

In `src/mpk_deck/ui/main_window.py`:

Import `BankHint`:

```python
from mpk_deck.ui.bank_hint import BankHint
```

`build_action_engine` signature — add `on_trigger`:

```python
def build_action_engine(config: DeckConfig, on_bank_changed, on_continuous, on_trigger) -> ActionEngine:
    engine = ActionEngine(on_bank_changed=on_bank_changed, on_continuous=on_continuous, on_trigger=on_trigger)
    ...
```

In `MainWindow.__init__`, update the engine construction:

```python
        self._engine = build_action_engine(
            self._config, self._on_bank_changed, self._on_joystick_continuous, self._on_trigger
        )
```

Update the controller construction to pass `on_bank_b_pad`:

```python
        self._midi = MPKController(self._engine, on_bank_b_pad=self._on_bank_b_pad)
```

Create the banner overlay near the other overlays (after `self._bank_indicator = ...`):

```python
        self._bank_hint = BankHint(self)
        self._bank_hint.set_accent(self._accent_hex)
```

Wire the two ExpandedView signals in `__init__` where the other `_expanded_view` connects are:

```python
        self._expanded_view.decorative_button_activated.connect(self._on_decorative_button)
        self._expanded_view.knob_locked_activated.connect(self._on_knob_locked)
```

Position the banner in `_position_overlay_widgets` (top-centre, below the top edge):

```python
        hint = self._bank_hint
        hint.move((self.width() - hint.width()) // 2, STATUS_DOT_MARGIN)
        hint.raise_()
```

Add the new slots (all marshalled onto the Qt thread — `on_trigger` and `on_bank_b_pad` can arrive on the MIDI callback thread, same as `_on_bank_changed`):

```python
    def _on_trigger(self, control: str, ok: bool) -> None:
        QTimer.singleShot(0, lambda: self._apply_trigger_flash(control, ok))

    def _apply_trigger_flash(self, control: str, ok: bool) -> None:
        view = self._mini_view if self._mode == "mini" else self._expanded_view
        view.flash_control(control, ok)

    def _on_bank_b_pad(self) -> None:
        QTimer.singleShot(0, self._bank_hint.show_hint)

    def _on_decorative_button(self, control: str) -> None:
        QMessageBox.information(
            self, "설정 불가",
            "이 버튼은 MIDI를 전송하지 않아 기능을 설정할 수 없습니다.",
        )

    def _on_knob_locked(self) -> None:
        QMessageBox.information(
            self, "설정 불가",
            "1번 노브는 조이스틱 Y축과 같은 신호(CC1)라서 따로 설정할 수 없습니다.",
        )
```

Add `QMessageBox` to the `PySide6.QtWidgets` import line.

Extend `_apply_joystick_continuous` so `joystick_y` also drives the knob-1 dial. Find the existing branch that handles `joystick_x`/`joystick_y` and add, after it updates `set_joystick_deflection`:

```python
        if control == "joystick_y":
            self._expanded_view.set_knob_value("knob_1", (value + 1.0) / 2.0)
```

Extend `_apply_design` to keep the banner's accent in sync:

```python
    def _apply_design(self) -> None:
        self._mini_view.set_accent(self._accent_hex)
        self._expanded_view.set_accent(self._accent_hex)
        self._expanded_view.set_knob_style(self._knob_style)
        self._bank_indicator.set_accent(self._accent_hex)
        self._bank_hint.set_accent(self._accent_hex)
```

- [ ] **Step 4: Run the smoke script**

Run: `python scratchpad/f_task8_smoke.py`
Expected: `OK`.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS (all ~180 tests). If `tests/` constructs `build_action_engine` directly, update those call sites to pass a fourth arg (`on_trigger=None` is not allowed positionally — pass `lambda *a: None` or `None`); grep first: `grep -rn build_action_engine tests/`.

- [ ] **Step 6: Manual live-check note for the executor**

Add a line to the task's completion note: the user must verify on real hardware — every pad/key/knob 2–8/joystick axis drives its widget and binding; function buttons are inert and show the message on double-click; a deliberately failing binding flashes red; switching the device to Bank B raises the banner.

- [ ] **Step 7: Commit**

```bash
git add src/mpk_deck/ui/main_window.py
git commit -m "feat(ui): wire hardware trigger flash, knob-1 mirror, Bank B banner"
```

---

## Task 9: Documentation — mark F done, defer the rest

**Files:**
- Modify: `ROADMAP.md`, `src/mpk_deck/CLAUDE.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update `src/mpk_deck/CLAUDE.md`**

In the "다음 라운드" section, mark item **F** done (mirror the style of the completed A/B/C entries): factory MIDI mapping used as-is (no editor), keybed notes 48–72 → `key_0`–`key_24`, CC1 → `joystick_y` only (knob 1 mirrors it, not configurable), pads assumed Bank A (36–43), function buttons decorative, `on_trigger` pass/fail flash, Bank B hint banner. Note the documented limitation (octave-shifted keybed notes outside 48–72 are dropped).

Update the "실제 아키텍처" section: `translate()` now maps the keybed range and drops out-of-range notes; `is_bank_b_pad_note()` exists; `ActionEngine` takes `on_trigger`; `MPKController` takes `on_bank_b_pad`.

- [ ] **Step 2: Update `ROADMAP.md`**

- Check off **F** in the mpk-deck "Next round" checklist.
- Add a new sub-list under mpk-deck for the deferred items (not started), each one line: per-bank vs. global/inherited bindings; function-label display modes (text/abbrev/icon); hover tooltips; pad icon design; chord input (multiple keys held → one action). Note D (knob volume/brightness) and E (knob mouse-wheel) are still the pre-existing next items.
- Add a Decision Log entry dated 2026-08-29 summarising: F shipped with the factory MIDI map and no editor changes; the CC1 knob-1/joystick-Y collision and the Bank A/B pad-note overlap are handled by convention + a hint, not by device config; function buttons transmit no MIDI so they are decorative.

- [ ] **Step 3: Verify the suite still passes and nothing else changed**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add ROADMAP.md src/mpk_deck/CLAUDE.md
git commit -m "docs: record sub-project F (hardware wiring) landing"
```

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|---|---|
| Keybed 48–72 → `key_0`–`key_24`, drop out-of-range | Task 1 |
| Drop `1: knob_1` from `KNOB_CC_TO_CONTROL` | Task 1 |
| `KEYBED_BASE_NOTE` / key-count constants | Task 1 |
| Bank B detection (`is_bank_b_pad_note`, 44–47 only) | Task 1 (predicate), Task 3 (controller fan-out), Task 7 + 8 (banner) |
| `ActionEngine.on_trigger(control, bool)`, catch handler exceptions, skip unbound/no-handler, `switch_bank` = ok | Task 2 |
| Handlers keep raising | Task 2 (no handler change) |
| Function buttons decorative + "no MIDI" message on double-click | Task 4 (widget), Task 8 (message) |
| Knob 1 mirrors joystick Y | Task 8 |
| Knob 1 double-click blocked with message; knobs 2–8 configurable | Task 5 (widget), Task 8 (message) |
| Green/red trigger flash on pads + keys, one reused QTimer per widget | Task 6 |
| MiniView pad flash in Mini mode | Task 6 + Task 8 (dispatch to visible view) |
| Bank B transient banner (auto-hide, re-arm, non-blocking) | Task 7 + Task 8 |
| `MPKController.on_bank_b_pad` kwarg | Task 3 |
| Marshalling MIDI-thread callbacks onto the Qt thread | Task 8 (`QTimer.singleShot(0, ...)`) |
| Out-of-scope items → ROADMAP | Task 9 |
| Test plan (pytest for logic, smoke for widgets, live for hardware) | every task's steps |

No gaps.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Every code step has literal code. The two "Plan step decides" phrases in the spec were replaced with concrete choices here (decorative message via a dedicated signal + `QMessageBox`; MIDI-layer constants defined locally, not imported from `ui/`).

**3. Type consistency:**
- `on_trigger` is `Callable[[str, bool], None]` in Task 2 and called as `self._on_trigger(control, ok)`; MainWindow's slot is `_on_trigger(self, control: str, ok: bool)` in Task 8. ✓
- `flash_control(control: str, ok: bool)` identical on `MiniView` (Task 6) and `ExpandedView` (Task 6), called with `(control, ok)` in Task 8. ✓
- `flash(ok: bool)` identical on `PadButton` and `_DebouncedKey` (Task 6). ✓
- `is_bank_b_pad_note(message)` defined in Task 1, imported in Task 3. ✓
- `decorative_button_activated = Signal(str)` (Task 4) / `knob_locked_activated = Signal()` (Task 5) connected in Task 8 to `_on_decorative_button(str)` / `_on_knob_locked()`. ✓
- `BankHint.show_hint()` / `set_accent()` / `_hide_timer` (Task 7) used in Task 8. ✓
- `build_action_engine` gains a 4th positional param `on_trigger` in Task 8; the self-review note in Task 8 Step 5 flags updating any test call sites.
