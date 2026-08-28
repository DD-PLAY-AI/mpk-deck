# Joystick Scroll + Visual Movement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MPK mini MK2's physical joystick scroll whatever window the user is working in (X = horizontal, Y = vertical, deflection-proportional speed, per-axis sensitivity), and make `ExpandedView`'s on-screen joystick visually mirror that deflection.

**Architecture:** `midi/translator.py` decodes `pitchwheel` (X) and a new `JOYSTICK_Y_CC` control-change (Y) into two ordinary continuous controls, `joystick_x`/`joystick_y`. `core/action_engine.py` gains a second injected callback, `on_continuous`, fired on every `set_continuous()` call regardless of binding state, so the UI can mirror live values without becoming part of the action-dispatch path. `core/handlers.py` gains `scroll_horizontal`/`scroll_vertical`, which inject real `SendInput`-class wheel events (not `PostMessage`, which many apps ignore) — this only works correctly because mouse-drag on the on-screen joystick never calls these handlers, so the real OS cursor is never sitting on mpk-deck's own window when a scroll fires. `MainWindow` owns a small repeat timer (only runs while deflected) so holding the stick keeps scrolling even though MIDI only sends on position change. `ExpandedView`'s joystick becomes a purpose-built `JoystickWidget`: mouse drag moves the handle for visual preview only (no engine calls), hardware input moves it through the same `set_deflection` method via `on_continuous`, and double-click opens a small per-axis configure menu reusing the existing `ActionConfigDialog`.

**Tech Stack:** No new dependencies — `win32api`/`win32con` (pywin32, already a runtime dependency) for the real wheel injection.

**Spec:** `docs/superpowers/specs/2026-08-28-joystick-scroll-design.md`

## Global Constraints

- `joystick_x`/`joystick_y` are ordinary continuous controls stored through the normal Action Registry/`Binding` system — never hardcoded — and in principle any control could be bound to `scroll_horizontal`/`scroll_vertical`, same as any other registered continuous action.
- Value range for `joystick_x`/`joystick_y` is **-1.0..1.0** (bipolar deflection from center), deliberately different from knobs' existing **0.0..1.0** (absolute dial position). Neither `ActionEngine` nor `ContinuousHandler`'s type signature cares about a handler's value range.
- Mouse drag on `ExpandedView`'s on-screen joystick widget is **visual-only** — it must never call `ActionEngine.set_continuous()` or otherwise trigger a scroll. Only hardware input (via `MPKController` -> `translate()` -> `engine.set_continuous()`) drives real scrolling.
- `handlers.py`'s scroll handlers use real `win32api.mouse_event(...)`/`SendInput`-class wheel injection, never `PostMessage` (many apps, especially Chrome/Electron, ignore synthetic non-injected wheel messages — see design doc).
- `midi/translator.py` checks the new `JOYSTICK_Y_CC` **before** `KNOB_CC_TO_CONTROL`: if the real hardware's joystick Y axis and `knob_1` really do collide on the same CC number, the joystick wins by default (this sub-project's whole purpose), and `knob_1` becomes unreachable via that CC until a live test resolves it with a one-line constant change.
- `MainWindow`'s repeat-while-held timer (`JOYSTICK_TIMER_INTERVAL_MS = 50`) only runs while at least one axis is non-zero, and stops the instant both are back to zero — no idle polling, matching the project's CPU/RAM-minimal constraint.
- `core/action_engine.py`: plain Python, zero Qt dependency — `on_continuous` is a plain injected callback, not a Qt signal, same pattern as `on_bank_changed`.
- `midi/translator.py`, `core/action_engine.py`, `core/handlers.py`, `ui/joystick_geometry.py`: pytest-covered (TDD). `ui/expanded_view.py` (`JoystickWidget`), `ui/action_config_dialog.py`, `ui/main_window.py`: not pytest-covered per this repo's documented policy (`mpk-deck/CLAUDE.md`) — verify manually via `python -m mpk_deck` or an off-screen smoke script.
- No git worktree — commit and push directly to `main` after each task (solo project, standing authorization per `mpk-deck/CLAUDE.md`, established 2026-08-19).

---

### Task 1: `midi/translator.py` — pitchwheel (X) and joystick-Y CC decoding

**Files:**
- Modify: `src/mpk_deck/midi/translator.py`
- Modify: `tests/midi/test_translator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: new module constant `JOYSTICK_Y_CC = 1`. `translate()` now also handles `message.type == "pitchwheel"` (-> `control="joystick_x"`) and `message.control == JOYSTICK_Y_CC` control_change messages (-> `control="joystick_y"`), both `kind="continuous"`, `value` in `-1.0..1.0`. `ControlEvent`, `PAD_NOTE_TO_CONTROL`, `KNOB_CC_TO_CONTROL` are unchanged.

- [ ] **Step 1: Replace the test file**

Replace the entire contents of `tests/midi/test_translator.py` with:

```python
import mido
import pytest

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
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/midi/test_translator.py -v`
Expected: the 8 pre-existing-style tests pass (the modified knob test still passes against unchanged code, since CC2 isn't touched yet); the 7 new pitchwheel/joystick_y tests FAIL (pitchwheel messages currently return `None`, and CC1 currently resolves to `knob_1`, not `joystick_y`).

- [ ] **Step 3: Implement the new decoding**

Replace the entire contents of `src/mpk_deck/midi/translator.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/midi/test_translator.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/midi/translator.py tests/midi/test_translator.py
git commit -m "feat: decode joystick pitchwheel/CC into joystick_x/joystick_y control events"
git push
```

---

### Task 2: `core/action_engine.py` — `on_continuous` callback

**Files:**
- Modify: `src/mpk_deck/core/action_engine.py`
- Modify: `tests/core/test_action_engine.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ActionEngine(on_bank_changed=None, on_continuous: Callable[[str, float], None] | None = None)`. `set_continuous(control, value)` now calls `on_continuous(control, value)` (if one was provided) unconditionally, before doing its existing binding/handler lookup — fires even for an unbound control or a control with no registered handler. Every other method's signature is unchanged.

- [ ] **Step 1: Add the failing tests**

Append to the end of `tests/core/test_action_engine.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_action_engine.py -v`
Expected: the 12 pre-existing tests pass; the 3 new `on_continuous` tests FAIL with `TypeError: __init__() got an unexpected keyword argument 'on_continuous'`.

- [ ] **Step 3: Add the callback**

In `src/mpk_deck/core/action_engine.py`, replace:

```python
    def __init__(self, on_bank_changed: Optional[Callable[[str], None]] = None) -> None:
        self._trigger_handlers: dict[str, TriggerHandler] = {}
        self._continuous_handlers: dict[str, ContinuousHandler] = {}
        self._bindings_by_control: dict[str, Binding] = {}
        self._banks: dict[str, list[Binding]] = {}
        self._switch_bindings: dict[str, str] = {}
        self._active_bank: str = ""
        self._on_bank_changed = on_bank_changed
```

with:

```python
    def __init__(
        self,
        on_bank_changed: Optional[Callable[[str], None]] = None,
        on_continuous: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        self._trigger_handlers: dict[str, TriggerHandler] = {}
        self._continuous_handlers: dict[str, ContinuousHandler] = {}
        self._bindings_by_control: dict[str, Binding] = {}
        self._banks: dict[str, list[Binding]] = {}
        self._switch_bindings: dict[str, str] = {}
        self._active_bank: str = ""
        self._on_bank_changed = on_bank_changed
        self._on_continuous = on_continuous
```

Then replace:

```python
    def set_continuous(self, control: str, value: float) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            return
        handler = self._continuous_handlers.get(binding.action)
        if handler is None:
            logger.warning("no continuous handler registered for action %s", binding.action)
            return
        handler(binding.params, value)
```

with:

```python
    def set_continuous(self, control: str, value: float) -> None:
        if self._on_continuous is not None:
            self._on_continuous(control, value)
        binding = self._bindings_by_control.get(control)
        if binding is None:
            return
        handler = self._continuous_handlers.get(binding.action)
        if handler is None:
            logger.warning("no continuous handler registered for action %s", binding.action)
            return
        handler(binding.params, value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_action_engine.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/action_engine.py tests/core/test_action_engine.py
git commit -m "feat: add on_continuous callback to ActionEngine"
git push
```

---

### Task 3: `core/handlers.py` — `scroll_horizontal`/`scroll_vertical`

**Files:**
- Modify: `src/mpk_deck/core/handlers.py`
- Modify: `tests/core/test_handlers.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `scroll_horizontal(params: dict, value: float, *, sender=None) -> None`, `scroll_vertical(params: dict, value: float, *, sender=None) -> None` — both `ContinuousHandler`-shaped (`(dict, float) -> None`), matching `core/action_registry.py`'s `default_joystick_bindings()` action names (Task 4) and `ui/main_window.py`'s `engine.register_continuous(...)` calls (Task 8). `sender` is injectable like `focus_window`'s `finder`/`set_system_volume`'s `volume_setter`; its default calls real `win32api`.

- [ ] **Step 1: Add the failing tests**

Append to the end of `tests/core/test_handlers.py`:

```python
def test_scroll_notches_scales_linearly_with_sensitivity():
    assert handlers._scroll_notches(1.0, 1.0) == 3
    assert handlers._scroll_notches(1.0, 2.0) == 6


def test_scroll_notches_negative_value_gives_negative_notches():
    assert handlers._scroll_notches(-1.0, 1.0) == -3


def test_scroll_notches_small_deflection_gives_fewer_notches():
    assert handlers._scroll_notches(0.1, 1.0) == 0
    assert handlers._scroll_notches(0.5, 1.0) == round(0.5 * 3)


def test_scroll_notches_clamps_out_of_range_value():
    assert handlers._scroll_notches(5.0, 1.0) == 3
    assert handlers._scroll_notches(-5.0, 1.0) == -3


def test_scroll_horizontal_calls_sender_with_horizontal_true():
    calls = []
    handlers.scroll_horizontal({"sensitivity": 1.0}, 1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": True, "notches": 3}]


def test_scroll_vertical_calls_sender_with_horizontal_false():
    calls = []
    handlers.scroll_vertical({"sensitivity": 1.0}, -1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": False, "notches": -3}]


def test_scroll_horizontal_zero_deflection_does_not_call_sender():
    calls = []
    handlers.scroll_horizontal({"sensitivity": 1.0}, 0.0, sender=lambda **kw: calls.append(kw))
    assert calls == []


def test_scroll_horizontal_missing_sensitivity_defaults_to_one():
    calls = []
    handlers.scroll_horizontal({}, 1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": True, "notches": 3}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_handlers.py -v`
Expected: the 9 pre-existing tests pass; the 8 new scroll tests FAIL with `AttributeError: module 'mpk_deck.core.handlers' has no attribute '_scroll_notches'` (or `scroll_horizontal`).

- [ ] **Step 3: Implement the handlers**

Append to the end of `src/mpk_deck/core/handlers.py`:

```python
def scroll_horizontal(params: dict, value: float, *, sender=None) -> None:
    """`value` in [-1.0, 1.0]: joystick X deflection, 0 = centered/no scroll.
    `params["sensitivity"]` (float, default 1.0) scales the notch count."""
    send = sender or _default_scroll_sender
    ticks = _scroll_notches(value, params.get("sensitivity", 1.0))
    if ticks:
        send(horizontal=True, notches=ticks)


def scroll_vertical(params: dict, value: float, *, sender=None) -> None:
    """Same as scroll_horizontal but for the vertical wheel."""
    send = sender or _default_scroll_sender
    ticks = _scroll_notches(value, params.get("sensitivity", 1.0))
    if ticks:
        send(horizontal=False, notches=ticks)


def _scroll_notches(value: float, sensitivity: float, *, max_notches: int = 3) -> int:
    """Pure: deflection + sensitivity -> whole wheel notches for one call. Linear in
    |value| so a light push scrolls slowly and a full push scrolls fast; sign gives
    direction."""
    return round(max(-1.0, min(1.0, value)) * sensitivity * max_notches)


def _default_scroll_sender(*, horizontal: bool, notches: int) -> None:
    """Real SendInput-class wheel injection - the OS treats it like a physical mouse
    wheel, unlike a PostMessage (which many apps, especially Chrome/Electron, ignore).
    Lands on whatever window the OS cursor is actually over - in real use that's
    always the app the user is working in, since mouse-drag on the on-screen joystick
    never calls this (see docs/superpowers/specs/2026-08-28-joystick-scroll-design.md)."""
    import win32api
    import win32con

    flag = win32con.MOUSEEVENTF_HWHEEL if horizontal else win32con.MOUSEEVENTF_WHEEL
    win32api.mouse_event(flag, 0, 0, notches * 120, 0)  # WHEEL_DELTA = 120 per notch
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_handlers.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/handlers.py tests/core/test_handlers.py
git commit -m "feat: add scroll_horizontal/scroll_vertical handlers (real SendInput wheel injection)"
git push
```

---

### Task 4: `core/action_registry.py` — default joystick bindings + backfill migration

**Files:**
- Modify: `src/mpk_deck/core/action_registry.py`
- Modify: `tests/core/test_action_registry.py`

**Interfaces:**
- Consumes: `Binding` (unchanged, this file).
- Produces: `default_joystick_bindings() -> list[Binding]` (a fresh list every call — two `Binding`s, `joystick_x` -> `scroll_horizontal` and `joystick_y` -> `scroll_vertical`, both `params={"sensitivity": 1.0}`), used by `load_config` (this task, for backfilling) and by `ui/main_window.py` (Task 8, for seeding brand-new banks). `load_config` now guarantees every bank it returns has bindings for both `joystick_x` and `joystick_y` — injecting the defaults only for whichever axis a bank's own bindings don't already cover, non-destructively (in memory only, same as the existing flat-format migration; nothing is written back until the next real save).

- [ ] **Step 1: Replace the test file**

Replace the entire contents of `tests/core/test_action_registry.py` with:

```python
from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    DEFAULT_BANK_ID,
    DEFAULT_BANK_NAME,
    DEFAULT_SWITCH_CONTROL,
    default_joystick_bindings,
    generate_bank_id,
    load_config,
    save_config,
)


def test_generate_bank_id_slugifies_name():
    assert generate_bank_id("Trading", existing_ids=[]) == "trading"


def test_generate_bank_id_replaces_non_alnum_with_underscore():
    assert generate_bank_id("My Cool Bank!", existing_ids=[]) == "my_cool_bank"


def test_generate_bank_id_dedupes_on_collision():
    assert generate_bank_id("Trading", existing_ids=["trading"]) == "trading_2"
    assert generate_bank_id("Trading", existing_ids=["trading", "trading_2"]) == "trading_3"


def test_generate_bank_id_blank_name_falls_back_to_bank():
    assert generate_bank_id("   ", existing_ids=[]) == "bank"


def test_default_joystick_bindings_covers_both_axes():
    bindings = default_joystick_bindings()
    by_control = {b.control: b for b in bindings}
    assert by_control["joystick_x"] == Binding(
        control="joystick_x", type="continuous", action="scroll_horizontal", params={"sensitivity": 1.0}
    )
    assert by_control["joystick_y"] == Binding(
        control="joystick_y", type="continuous", action="scroll_vertical", params={"sensitivity": 1.0}
    )


def test_default_joystick_bindings_returns_a_fresh_list_each_call():
    a = default_joystick_bindings()
    a.append(Binding(control="x", type="trigger", action="y", params={}))
    assert len(default_joystick_bindings()) == 2


def test_load_config_missing_file_returns_default_seed(tmp_path):
    config = load_config(tmp_path / "nope.yaml")
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}


def test_load_config_empty_file_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("")
    config = load_config(path)
    assert config.banks[DEFAULT_BANK_ID].name == DEFAULT_BANK_NAME


def test_load_config_malformed_yaml_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks: [this is not: valid: yaml: at all")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_migrates_old_flat_format(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: trigger\n"
        "    action: launch_program\n"
        '    params: { path: "C:/x.exe" }\n'
    )
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks[DEFAULT_BANK_ID].name == DEFAULT_BANK_NAME
    assert config.banks[DEFAULT_BANK_ID].bindings == [
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"}),
        *default_joystick_bindings(),
    ]


def test_load_config_migration_skips_invalid_entry(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: bogus_type\n"
        "    action: launch_program\n"
        "  - control: pad_2\n"
        "    type: trigger\n"
        "    action: open_url\n"
        '    params: { url: "https://example.com" }\n'
    )
    config = load_config(path)
    non_joystick = [b for b in config.banks[DEFAULT_BANK_ID].bindings if b.control not in ("joystick_x", "joystick_y")]
    assert len(non_joystick) == 1
    assert non_joystick[0].control == "pad_2"


def test_load_config_parses_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "active_bank: bank_b\n"
        "switch_bindings:\n"
        "  key_0: bank_a\n"
        "banks:\n"
        "  bank_a:\n"
        "    name: Home\n"
        "    bindings: []\n"
        "  bank_b:\n"
        "    name: Trading\n"
        "    bindings:\n"
        "      - control: pad_1\n"
        "        type: trigger\n"
        "        action: open_url\n"
        '        params: { url: "https://example.com" }\n'
    )
    config = load_config(path)
    assert config.active_bank == "bank_b"
    assert config.switch_bindings == {"key_0": "bank_a"}
    assert config.banks["bank_a"] == Bank(name="Home", bindings=default_joystick_bindings())
    assert config.banks["bank_b"].name == "Trading"
    assert config.banks["bank_b"].bindings == [
        Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://example.com"}),
        *default_joystick_bindings(),
    ]


def test_load_config_non_mapping_top_level_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("- just\n- a\n- list\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_bank_entry_not_a_mapping_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\n  bank_a: not_a_mapping\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_switch_bindings_not_a_mapping_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\n  bank_a:\n    name: Home\n    bindings: []\nswitch_bindings:\n  - a\n  - b\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_null_banks_seeds_default_bank(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\nactive_bank: bank_a\n")
    config = load_config(path)
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}


def test_load_config_active_bank_not_in_banks_falls_back(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("active_bank: ghost\nbanks:\n  bank_a:\n    name: Home\n    bindings: []\n")
    config = load_config(path)
    assert config.active_bank == "bank_a"


def test_load_config_preserves_existing_joystick_binding_instead_of_backfilling(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "active_bank: bank_a\n"
        "switch_bindings: {}\n"
        "banks:\n"
        "  bank_a:\n"
        "    name: Home\n"
        "    bindings:\n"
        "      - control: joystick_x\n"
        "        type: continuous\n"
        "        action: scroll_horizontal\n"
        "        params: { sensitivity: 2.5 }\n"
    )
    config = load_config(path)
    bindings = config.banks["bank_a"].bindings
    joystick_x = [b for b in bindings if b.control == "joystick_x"]
    joystick_y = [b for b in bindings if b.control == "joystick_y"]
    assert len(joystick_x) == 1
    assert joystick_x[0].params == {"sensitivity": 2.5}
    assert len(joystick_y) == 1  # still backfilled - only joystick_x was customized


def test_save_then_load_round_trips_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    config = DeckConfig(
        active_bank="bank_b",
        switch_bindings={"key_0": "bank_a"},
        banks={
            "bank_a": Bank(name="Home", bindings=default_joystick_bindings()),
            "bank_b": Bank(
                name="Trading",
                bindings=[
                    Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://x.com"}),
                    *default_joystick_bindings(),
                ],
            ),
        },
    )
    save_config(path, config)
    assert load_config(path) == config
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_action_registry.py -v`
Expected: the `generate_bank_id` tests still pass; every test that touches `default_joystick_bindings` FAILs with `ImportError: cannot import name 'default_joystick_bindings'`.

- [ ] **Step 3: Add `default_joystick_bindings`, backfill, and wire it into every seed/parse path**

In `src/mpk_deck/core/action_registry.py`, add right after `generate_bank_id`'s function body (before `_parse_bindings_list`):

```python
DEFAULT_JOYSTICK_SENSITIVITY = 1.0


def default_joystick_bindings() -> list[Binding]:
    """Every bank should scroll out of the box - see docs/superpowers/specs/
    2026-08-28-joystick-scroll-design.md. Returns a fresh list every call; Binding
    is frozen but the containing list must never be shared/mutated across banks."""
    return [
        Binding(
            control="joystick_x",
            type="continuous",
            action="scroll_horizontal",
            params={"sensitivity": DEFAULT_JOYSTICK_SENSITIVITY},
        ),
        Binding(
            control="joystick_y",
            type="continuous",
            action="scroll_vertical",
            params={"sensitivity": DEFAULT_JOYSTICK_SENSITIVITY},
        ),
    ]


def _backfill_joystick_bindings(bindings: list[Binding]) -> list[Binding]:
    controls = {b.control for b in bindings}
    return bindings + [b for b in default_joystick_bindings() if b.control not in controls]
```

Then replace `_default_config`:

```python
def _default_config() -> DeckConfig:
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())},
    )
```

In `load_config`, replace the old-flat-format migration tail:

```python
    # old flat format (or an empty/near-empty file) -> migrate
    raw_bindings = data.get("bindings", []) or []
    bindings = _parse_bindings_list(raw_bindings)
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=bindings)},
    )
```

with:

```python
    # old flat format (or an empty/near-empty file) -> migrate
    raw_bindings = data.get("bindings", []) or []
    bindings = _backfill_joystick_bindings(_parse_bindings_list(raw_bindings))
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=bindings)},
    )
```

Finally, replace `_parse_new_format`:

```python
def _parse_new_format(data: dict) -> DeckConfig:
    banks = {}
    for bank_id, bank_data in (data.get("banks") or {}).items():
        raw_bindings = bank_data.get("bindings", []) or []
        banks[bank_id] = Bank(name=bank_data.get("name", bank_id), bindings=_parse_bindings_list(raw_bindings))
    if not banks:
        banks = {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])}
    switch_bindings = dict(data.get("switch_bindings") or {})
    active_bank = data.get("active_bank") or DEFAULT_BANK_ID
    if active_bank not in banks:
        active_bank = next(iter(banks))
    return DeckConfig(active_bank=active_bank, switch_bindings=switch_bindings, banks=banks)
```

with:

```python
def _parse_new_format(data: dict) -> DeckConfig:
    banks = {}
    for bank_id, bank_data in (data.get("banks") or {}).items():
        raw_bindings = bank_data.get("bindings", []) or []
        bindings = _backfill_joystick_bindings(_parse_bindings_list(raw_bindings))
        banks[bank_id] = Bank(name=bank_data.get("name", bank_id), bindings=bindings)
    if not banks:
        banks = {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}
    switch_bindings = dict(data.get("switch_bindings") or {})
    active_bank = data.get("active_bank") or DEFAULT_BANK_ID
    if active_bank not in banks:
        active_bank = next(iter(banks))
    return DeckConfig(active_bank=active_bank, switch_bindings=switch_bindings, banks=banks)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_action_registry.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/action_registry.py tests/core/test_action_registry.py
git commit -m "feat: seed/backfill default joystick scroll bindings on every bank"
git push
```

---

### Task 5: `ui/joystick_geometry.py` — mouse-drag clamp math

**Files:**
- Create: `src/mpk_deck/ui/joystick_geometry.py`
- Test: `tests/ui/test_joystick_geometry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `clamp_deflection(dx: float, dy: float, max_radius: float) -> tuple[float, float]` — used only by `JoystickWidget`'s mouse-drag preview path (Task 6), never by the hardware path (translator values already arrive pre-normalized).

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/test_joystick_geometry.py`:

```python
import pytest

from mpk_deck.ui.joystick_geometry import clamp_deflection


def test_clamp_deflection_center_returns_zero():
    assert clamp_deflection(0.0, 0.0, 20.0) == (0.0, 0.0)


def test_clamp_deflection_inside_circle_normalizes_without_clamping():
    x, y = clamp_deflection(10.0, 0.0, 20.0)
    assert x == 0.5
    assert y == 0.0


def test_clamp_deflection_on_boundary_normalizes_to_one():
    x, y = clamp_deflection(0.0, -20.0, 20.0)
    assert x == 0.0
    assert y == -1.0


def test_clamp_deflection_outside_circle_is_clamped_to_radius():
    x, y = clamp_deflection(40.0, 0.0, 20.0)
    assert x == pytest.approx(1.0)
    assert y == pytest.approx(0.0, abs=1e-9)


def test_clamp_deflection_diagonal_outside_circle_preserves_direction():
    x, y = clamp_deflection(30.0, 30.0, 20.0)
    magnitude = (x * x + y * y) ** 0.5
    assert magnitude == pytest.approx(1.0)
    assert x == pytest.approx(y)


def test_clamp_deflection_zero_radius_returns_zero():
    assert clamp_deflection(5.0, 5.0, 0.0) == (0.0, 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_joystick_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mpk_deck.ui.joystick_geometry'`

- [ ] **Step 3: Implement it**

Create `src/mpk_deck/ui/joystick_geometry.py`:

```python
def clamp_deflection(dx: float, dy: float, max_radius: float) -> tuple[float, float]:
    """Clamp a raw pixel offset from center to a circle of max_radius, return axes
    normalized to [-1.0, 1.0] on each dimension. (0.0, 0.0) if max_radius <= 0."""
    if max_radius <= 0:
        return (0.0, 0.0)
    distance = (dx * dx + dy * dy) ** 0.5
    if distance > max_radius:
        scale = max_radius / distance
        dx *= scale
        dy *= scale
    return (dx / max_radius, dy / max_radius)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_joystick_geometry.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/joystick_geometry.py tests/ui/test_joystick_geometry.py
git commit -m "feat: add clamp_deflection for the joystick mouse-drag preview"
git push
```

---

### Task 6: `ui/expanded_view.py` — `JoystickWidget`

**Files:**
- Modify: `src/mpk_deck/ui/expanded_view.py`

**Interfaces:**
- Consumes: `clamp_deflection` (Task 5).
- Produces: `JoystickWidget(QFrame)` — `set_deflection(x: float, y: float) -> None` (clamps to -1..1, repositions the handle; called both by mouse-drag internally and, via `ExpandedView.set_joystick_deflection`, from `MainWindow`'s hardware path), `axis_configure_requested = Signal(str)` (emits `"joystick_x"` or `"joystick_y"`), `apply_style(colors: dict[str, str], diameter: int) -> None`. `ExpandedView` gains `set_joystick_deflection(x: float, y: float) -> None`, delegating to the widget — this is what `MainWindow` (Task 8) calls. Replaces the old `self._joystick = PadButton("JOY", self)` and its `activated`/`configure_requested` wiring (the generic `"joystick"` control id is retired — confirmed via `grep -n joystick config/actions.yaml` finding no existing binding to migrate). No pytest coverage (Qt widget, per project policy) — verified in Step 5 below.

- [ ] **Step 1: Add the `QMenu` import and the `JoystickWidget` class**

In `src/mpk_deck/ui/expanded_view.py`, replace the whole import block at the top of the file:

```python
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX, ACCENT_RGB
from mpk_deck.ui.keybed import NUM_KEYS, compute_keybed_rects, is_black_key
from mpk_deck.ui.mini_view import PadButton
from mpk_deck.ui.scaling import compute_scale
from mpk_deck.ui.window_grip import WindowGripMixin
```

with:

```python
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMenu, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX, ACCENT_RGB
from mpk_deck.ui.joystick_geometry import clamp_deflection
from mpk_deck.ui.keybed import NUM_KEYS, compute_keybed_rects, is_black_key
from mpk_deck.ui.mini_view import PadButton
from mpk_deck.ui.scaling import compute_scale
from mpk_deck.ui.window_grip import WindowGripMixin
```

Add the `JoystickWidget` class right after `_DebouncedKey` (before `_button_qss`):

```python
class JoystickWidget(QFrame):
    """Visual-only joystick indicator. Mouse drag previews the handle position but
    never triggers a scroll - the OS cursor sits on this widget while dragging, so a
    real scroll here would land on mpk-deck's own window, not whatever app the user
    is working in (see docs/superpowers/specs/2026-08-28-joystick-scroll-design.md).
    Real hardware input drives both the visual position (via set_deflection, called
    from MainWindow's on_continuous callback) and the actual scroll (via ActionEngine,
    entirely outside this widget)."""

    axis_configure_requested = Signal(str)  # "joystick_x" or "joystick_y"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._handle = QFrame(self)
        self._x = 0.0
        self._y = 0.0

    def set_deflection(self, x: float, y: float) -> None:
        self._x = max(-1.0, min(1.0, x))
        self._y = max(-1.0, min(1.0, y))
        self._reposition_handle()

    def apply_style(self, colors: dict[str, str], diameter: int) -> None:
        self.setFixedSize(diameter, diameter)
        self.setStyleSheet(
            f"QFrame {{ background: {colors['fill']}; border: 2px solid {ACCENT_HEX}; "
            f"border-radius: {diameter // 2}px; }}"
        )
        self._handle.setStyleSheet(f"QFrame {{ background: {ACCENT_HEX}; border-radius: 999px; }}")
        self._reposition_handle()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._reposition_handle()

    def _reposition_handle(self) -> None:
        base_r = self.width() / 2
        handle_d = max(1, round(self.width() * 0.4))
        handle_r = handle_d / 2
        self._handle.setFixedSize(handle_d, handle_d)
        cx = base_r + self._x * (base_r - handle_r) - handle_r
        cy = base_r + self._y * (base_r - handle_r) - handle_r
        self._handle.move(round(cx), round(cy))

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from_mouse(event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_from_mouse(event.position())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.set_deflection(0.0, 0.0)
        super().mouseReleaseEvent(event)

    def _drag_from_mouse(self, pos) -> None:
        cx, cy = self.width() / 2, self.height() / 2
        x, y = clamp_deflection(pos.x() - cx, pos.y() - cy, self.width() / 2)
        self.set_deflection(x, y)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        menu = QMenu(self)
        x_action = menu.addAction("Horizontal (joystick_x)")
        y_action = menu.addAction("Vertical (joystick_y)")
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is x_action:
            self.axis_configure_requested.emit("joystick_x")
        elif chosen is y_action:
            self.axis_configure_requested.emit("joystick_y")
        super().mouseDoubleClickEvent(event)
```

- [ ] **Step 2: Swap the old `PadButton` joystick for `JoystickWidget`**

In `ExpandedView.__init__`, replace:

```python
        self._joystick = PadButton("JOY", self)
        self._joystick.activated.connect(lambda: self.control_activated.emit("joystick"))
        self._joystick.configure_requested.connect(lambda: self.control_configure_requested.emit("joystick"))
```

with:

```python
        self._joystick = JoystickWidget(self)
        self._joystick.axis_configure_requested.connect(self.control_configure_requested.emit)
```

- [ ] **Step 3: Add `set_joystick_deflection` to `ExpandedView`**

Add this method to `ExpandedView` (e.g. right after `set_dark`):

```python
    def set_joystick_deflection(self, x: float, y: float) -> None:
        self._joystick.set_deflection(x, y)
```

- [ ] **Step 4: Update `_layout_controls` to style the joystick through the new widget**

Replace:

```python
        joy_qss = (
            f"QPushButton {{ background: {colors['fill']}; border: 2px solid {ACCENT_HEX}; "
            f"border-radius: {joy_d // 2}px; color: {colors['text']}; font-size: {btn_font:.0f}px; "
            f"font-weight: 700; }}"
            f"QPushButton:hover {{ background: {colors['fill_hover']}; }}"
            f"QPushButton:pressed {{ background: {colors['fill_pressed']}; }}"
        )
        self._joystick.setStyleSheet(joy_qss)
        self._joystick.setFixedSize(joy_d, joy_d)
```

with:

```python
        self._joystick.apply_style(colors, joy_d)
```

(`btn_font` is still used a few lines below for `btn_qss = _button_qss(colors, btn_font, radius=4 * scale)` — don't remove its computation, only the `joy_qss` block above.)

- [ ] **Step 5: Verify via an off-screen smoke script**

Create a temporary script (not committed) at, e.g., `C:\Users\ehdck\AppData\Local\Temp\claude\C--DC-DD\acaa9204-6cf7-426b-a5b3-69afb2f65a1b\scratchpad\joystick_smoke.py`:

```python
import sys
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "C:/DC/DD/mpk-deck/src")
from mpk_deck.ui.expanded_view import ExpandedView

app = QApplication(sys.argv)
view = ExpandedView()
view.resize(960, 568)
view.show()
app.processEvents()

joy = view._joystick
center = joy.rect().center()
edge = QPointF(center.x() + joy.width() / 2, center.y())

press = QMouseEvent(QEvent.Type.MouseButtonPress, edge, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
app.sendEvent(joy, press)
print("after press at right edge:", joy._x, joy._y)
assert joy._x > 0.9 and abs(joy._y) < 0.1, "expected full-right deflection"

release = QMouseEvent(QEvent.Type.MouseButtonRelease, edge, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
app.sendEvent(joy, release)
print("after release:", joy._x, joy._y)
assert joy._x == 0.0 and joy._y == 0.0, "expected spring-back to center on release"

view.set_joystick_deflection(-0.5, 0.3)
print("after hardware-path set_joystick_deflection:", joy._x, joy._y)
assert joy._x == -0.5 and joy._y == 0.3

print("OK")
view.close()
```

Run: `python <path-to-script>`
Expected: prints the deflection values at each step, ends with `OK`, no assertion error, no crash.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/ui/expanded_view.py
git commit -m "feat: replace ExpandedView's joystick button with a visual-only JoystickWidget"
git push
```

---

### Task 7: `ui/action_config_dialog.py` — scroll actions + sensitivity

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`

**Interfaces:**
- Consumes: nothing new from other modules (action names `"scroll_horizontal"`/`"scroll_vertical"` are just strings, matching `core/handlers.py` (Task 3) and `core/action_registry.default_joystick_bindings()` (Task 4)).
- Produces: `ACTION_CHOICES` gains `scroll_horizontal`/`scroll_vertical` (both `ACTION_TYPE: "continuous"`, `PARAM_KEY: None`). `_apply_binding`/`result_binding` special-case these two actions to read/write `params={"sensitivity": float}` via a new numeric field instead of the generic `PARAM_KEY` text path. No pytest coverage (Qt widget) — verified in Step 4.

- [ ] **Step 1: Add the two action choices**

Replace:

```python
ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
    ("switch_bank", "➕", "Add Bank"),
]
ACTION_GLYPHS = {name: glyph for name, glyph, _ in ACTION_CHOICES}
ACTION_LABELS = {name: label for name, _, label in ACTION_CHOICES}
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
    "switch_bank": "trigger",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
    "switch_bank": None,
}
```

with:

```python
ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
    ("scroll_horizontal", "\u2194", "Scroll Horizontal"),
    ("scroll_vertical", "\u2195", "Scroll Vertical"),
    ("switch_bank", "➕", "Add Bank"),
]
ACTION_GLYPHS = {name: glyph for name, glyph, _ in ACTION_CHOICES}
ACTION_LABELS = {name: label for name, _, label in ACTION_CHOICES}
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
    "scroll_horizontal": "continuous",
    "scroll_vertical": "continuous",
    "switch_bank": "trigger",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
    "scroll_horizontal": None,
    "scroll_vertical": None,
    "switch_bank": None,
}
```

- [ ] **Step 2: Add the sensitivity param page**

Right after the existing line `self._bank_name_edit = self._build_bank_name_page()` in `__init__`, add:

```python
        self._sensitivity_edit = self._build_sensitivity_page()
```

Add the page-builder method next to the other `_build_*_page` methods (e.g. right after `_build_bank_name_page`):

```python
    def _build_sensitivity_page(self) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Scroll sensitivity (0.1 - 3.0, default 1.0):", page))
        edit = QLineEdit(page)
        edit.setText("1.0")
        layout.addWidget(edit)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit
```

- [ ] **Step 3: Update `_apply_binding` and `result_binding`**

Replace:

```python
    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
        if binding.action == "switch_bank":
            bank_id = binding.params.get("bank_id", "")
            self._bank_name_edit.setText(self._bank_names.get(bank_id, ""))
            return
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))
```

with:

```python
    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
        if binding.action == "switch_bank":
            bank_id = binding.params.get("bank_id", "")
            self._bank_name_edit.setText(self._bank_names.get(bank_id, ""))
            return
        if binding.action in ("scroll_horizontal", "scroll_vertical"):
            self._sensitivity_edit.setText(str(binding.params.get("sensitivity", 1.0)))
            return
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))
```

Replace:

```python
    def result_binding(self) -> Binding:
        action = self._current_action()
        if self._locked or action == "switch_bank":
            # The real bank_id is assigned by the caller (new bank, or the existing
            # locked control's target) - this dialog only ever supplies the name.
            return Binding(control=self._control, type="trigger", action="switch_bank", params={})
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text()} if key and edit else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)
```

with:

```python
    def result_binding(self) -> Binding:
        action = self._current_action()
        if self._locked or action == "switch_bank":
            # The real bank_id is assigned by the caller (new bank, or the existing
            # locked control's target) - this dialog only ever supplies the name.
            return Binding(control=self._control, type="trigger", action="switch_bank", params={})
        if action in ("scroll_horizontal", "scroll_vertical"):
            try:
                sensitivity = float(self._sensitivity_edit.text())
            except ValueError:
                sensitivity = 1.0
            sensitivity = max(0.1, min(3.0, sensitivity))
            return Binding(control=self._control, type="continuous", action=action, params={"sensitivity": sensitivity})
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text()} if key and edit else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)
```

- [ ] **Step 4: Verify it imports cleanly**

Run: `python -c "from mpk_deck.ui.action_config_dialog import ActionConfigDialog; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py
git commit -m "feat: add Scroll Horizontal/Vertical actions with configurable sensitivity"
git push
```

---

### Task 8: `MainWindow` — wire the joystick end-to-end

**Files:**
- Modify: `src/mpk_deck/ui/main_window.py`

**Interfaces:**
- Consumes: `scroll_horizontal`, `scroll_vertical` (Task 3), `default_joystick_bindings` (Task 4), `ActionEngine(on_continuous=...)` (Task 2), `ExpandedView.set_joystick_deflection` (Task 6).
- Produces: no new public interface — composition root wiring only.

- [ ] **Step 1: Update imports**

Replace:

```python
from mpk_deck.core.action_registry import Bank, Binding, DeckConfig, generate_bank_id, load_config, save_config
from mpk_deck.core.handlers import focus_window, launch_program, open_url, set_system_volume
```

with:

```python
from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    default_joystick_bindings,
    generate_bank_id,
    load_config,
    save_config,
)
from mpk_deck.core.handlers import focus_window, launch_program, open_url, scroll_horizontal, scroll_vertical, set_system_volume
```

- [ ] **Step 2: Add the joystick timer interval constant**

Replace:

```python
MIDI_POLL_INTERVAL_MS = 3000
STATUS_DOT_MARGIN = 10
```

with:

```python
MIDI_POLL_INTERVAL_MS = 3000
STATUS_DOT_MARGIN = 10
JOYSTICK_TIMER_INTERVAL_MS = 50  # 20Hz repeat-while-held; only runs while deflected
```

- [ ] **Step 3: Update `build_action_engine`**

Replace:

```python
def build_action_engine(config: DeckConfig, on_bank_changed) -> ActionEngine:
    engine = ActionEngine(on_bank_changed=on_bank_changed)
    engine.register_trigger("launch_program", launch_program)
    engine.register_trigger("open_url", open_url)
    engine.register_trigger("focus_window", focus_window)
    engine.register_continuous("set_system_volume", set_system_volume)
    engine.load_banks(
        {bank_id: bank.bindings for bank_id, bank in config.banks.items()},
        config.switch_bindings,
        config.active_bank,
    )
    return engine
```

with:

```python
def build_action_engine(config: DeckConfig, on_bank_changed, on_continuous) -> ActionEngine:
    engine = ActionEngine(on_bank_changed=on_bank_changed, on_continuous=on_continuous)
    engine.register_trigger("launch_program", launch_program)
    engine.register_trigger("open_url", open_url)
    engine.register_trigger("focus_window", focus_window)
    engine.register_continuous("set_system_volume", set_system_volume)
    engine.register_continuous("scroll_horizontal", scroll_horizontal)
    engine.register_continuous("scroll_vertical", scroll_vertical)
    engine.load_banks(
        {bank_id: bank.bindings for bank_id, bank in config.banks.items()},
        config.switch_bindings,
        config.active_bank,
    )
    return engine
```

- [ ] **Step 4: Wire the engine constructor call and the repeat timer**

Replace:

```python
        self._config = load_config(DEFAULT_ACTIONS_PATH)
        self._bank_names: dict[str, str] = {bank_id: bank.name for bank_id, bank in self._config.banks.items()}
        self._engine = build_action_engine(self._config, self._on_bank_changed)
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False
```

with:

```python
        self._config = load_config(DEFAULT_ACTIONS_PATH)
        self._bank_names: dict[str, str] = {bank_id: bank.name for bank_id, bank in self._config.banks.items()}
        self._joystick_values: dict[str, float] = {"joystick_x": 0.0, "joystick_y": 0.0}
        self._engine = build_action_engine(self._config, self._on_bank_changed, self._on_joystick_continuous)
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False

        self._joystick_timer = QTimer(self)
        self._joystick_timer.timeout.connect(self._on_joystick_timer_tick)
```

- [ ] **Step 5: Add the `on_continuous` callback, the visual-mirror apply, and the repeat-timer tick**

Add these methods to `MainWindow` (e.g. right after `_apply_bank_change`):

```python
    def _on_joystick_continuous(self, control: str, value: float) -> None:
        QTimer.singleShot(0, lambda: self._apply_joystick_continuous(control, value))

    def _apply_joystick_continuous(self, control: str, value: float) -> None:
        if control not in self._joystick_values:
            return
        self._joystick_values[control] = value
        self._expanded_view.set_joystick_deflection(
            self._joystick_values["joystick_x"], self._joystick_values["joystick_y"]
        )
        any_active = any(v != 0.0 for v in self._joystick_values.values())
        if any_active and not self._joystick_timer.isActive():
            self._joystick_timer.start(JOYSTICK_TIMER_INTERVAL_MS)
        elif not any_active and self._joystick_timer.isActive():
            self._joystick_timer.stop()

    def _on_joystick_timer_tick(self) -> None:
        for control, value in self._joystick_values.items():
            if value != 0.0:
                self._engine.set_continuous(control, value)
```

(`QTimer.singleShot(0, ...)` marshals off the MIDI callback thread onto the GUI thread — same pattern `_on_bank_changed`/`_apply_bank_change` already use, for the same reason.)

- [ ] **Step 6: Seed new banks with the default joystick bindings**

In `_save_bank_binding`, replace:

```python
        else:
            bank_id = generate_bank_id(bank_name, self._config.banks.keys())
            self._config.banks[bank_id] = Bank(name=bank_name, bindings=[])
            self._config.switch_bindings[control] = bank_id
```

with:

```python
        else:
            bank_id = generate_bank_id(bank_name, self._config.banks.keys())
            self._config.banks[bank_id] = Bank(name=bank_name, bindings=default_joystick_bindings())
            self._config.switch_bindings[control] = bank_id
```

- [ ] **Step 7: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (this task adds no new tests — `main_window.py` has no pytest coverage by project convention; this confirms nothing else broke from the import/signature changes).

- [ ] **Step 8: Manually verify — mouse-drag preview never scrolls**

Run: `python -m mpk_deck`, switch to Expanded mode. Click-and-drag the joystick with the mouse in any direction, watch the on-screen handle move, release and watch it spring back to center. Expected: the handle visually tracks the mouse and re-centers on release; nothing on the actual desktop scrolls while doing this (confirms the mouse path never reaches `ActionEngine.set_continuous`).

- [ ] **Step 9: Manually verify — double-click axis configure**

Double-click the joystick. Expected: a small menu appears with "Horizontal (joystick_x)" and "Vertical (joystick_y)". Pick one, expected: the normal `ActionConfigDialog` opens with "Scroll Horizontal" (or "Scroll Vertical") pre-selected and the sensitivity field showing `1.0` (today's default seed). Change the sensitivity value and Save; reopen the same axis's dialog and confirm the new value is shown (round-tripped through `config/actions.yaml`).

- [ ] **Step 10: Manually verify — every existing bank already has both axes bound**

Run: `type config\actions.yaml` (or open it in an editor). Expected: every bank under `banks:` now lists a `joystick_x` (`scroll_horizontal`) and a `joystick_y` (`scroll_vertical`) binding, including banks that existed before this sub-project (the backfill from Task 4 ran on load and was written back by Step 9's Save).

- [ ] **Step 11: Manually verify — real hardware, if the MPK mini MK2 is connected**

Run: `python -m mpk_deck` with the device plugged in. Move the physical joystick left/right/up/down. Expected: the on-screen `ExpandedView` joystick handle visually tracks the movement in real time, and whatever window currently has focus outside mpk-deck scrolls proportionally to how far the stick is pushed (light push = slow, full push = fast), continuing to scroll while held at a fixed deflection. If nothing happens on either axis, or moving the stick changes system volume instead (the `knob_1`/CC1 collision named in the design doc's Open Questions), note exactly what was observed — that's the live-test signal this plan's `JOYSTICK_Y_CC`/`KNOB_CC_TO_CONTROL` precedence decision is waiting on, not a bug in this task's code.

- [ ] **Step 12: Commit**

```bash
git add src/mpk_deck/ui/main_window.py
git commit -m "feat: wire joystick scroll and visual mirroring into MainWindow"
git push
```

---

### Task 9: Docs

**Files:**
- Modify: `mpk-deck/CLAUDE.md`
- Modify: `C:\DC\DD\ROADMAP.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `mpk-deck/CLAUDE.md`**

In the "다음 라운드" list, mark item **C** done (same style as A/B were marked) with a short summary: `joystick_x`/`joystick_y` as ordinary continuous controls seeded by default in every bank, `midi/translator.py`'s pitchwheel/CC decoding (and the `JOYSTICK_Y_CC`-before-`KNOB_CC_TO_CONTROL` precedence decision), the visual-only mouse-drag vs. real-`SendInput`-scroll hardware split, and the repeat-while-held timer. Note whether Step 11's live hardware check (Task 8) confirmed or contradicted the `JOYSTICK_Y_CC = 1` / `knob_1` collision guess, and update the "실제 아키텍처" section's `ActionEngine`/`handlers.py`/`translator.py` descriptions to mention `on_continuous`, `scroll_horizontal`/`scroll_vertical`, and the pitchwheel/joystick-Y decoding. Link to `docs/superpowers/specs/2026-08-28-joystick-scroll-design.md` and this plan file.

- [ ] **Step 2: Update `C:\DC\DD\ROADMAP.md`**

Check off item **C** under mpk-deck's "다음 라운드" list (same style as A/B), and add a Decision Log entry dated with today's date summarizing what shipped, whether live hardware testing (if the device was connected during Task 8 Step 11) confirmed the `JOYSTICK_Y_CC`/`knob_1` collision, and any deviations from the spec discovered during implementation (if none, say so explicitly).

- [ ] **Step 3: Commit**

```bash
git add "C:\DC\DD\mpk-deck\CLAUDE.md" "C:\DC\DD\ROADMAP.md"
git commit -m "docs: record joystick scroll landing"
git push
```

## Post-Plan Checklist

- [ ] Run the full suite once more: `pytest -v` — all tests (Tasks 1-5's new ones, plus every pre-existing test) should pass.
- [ ] `grep -rn "\"joystick\"" src/` returns nothing (the old generic single-`PadButton` joystick control id is fully retired, replaced by `joystick_x`/`joystick_y`).
- [ ] `python -m mpk_deck` still launches cleanly with the real `config/actions.yaml`, and the tray Quit still fully terminates the process (unaffected by this plan, worth re-confirming since `MainWindow.__init__` changed).
- [ ] Confirm no scratch smoke-test script from Task 6 Step 5 was accidentally committed: `git status`.
