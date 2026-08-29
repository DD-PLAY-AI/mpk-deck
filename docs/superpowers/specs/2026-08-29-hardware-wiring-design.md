# Sub-project F — Real MPK mini MK2 hardware wiring (design)

Date: 2026-08-29
Status: approved for planning
Predecessors: A (MIDI status), B (bank system), C (joystick scroll), ad-hoc
Design preferences — all shipped. This is the last item of the "everyday
deck" round decomposed 2026-08-25.

## Goal

Make every physical control on the AKAI MPK mini MK2 drive the deck
end-to-end, using the **factory MIDI mapping as-is** (no AKAI MPK mini
Editor changes), and reflect that input in the UI. Completion criteria:

- Pads, keys, knobs 2–8, and the joystick (both axes) trigger their bound
  actions and visibly move / flash in ExpandedView when operated on real
  hardware.
- Controls that the MK2 does not expose over MIDI (the function buttons)
  are visibly inert in the UI and say so when the user tries to configure
  them.
- Action execution shows a pass/fail result.
- Unplugging the device mid-session does not disrupt anything (already
  handled by `db8b8d1`; F only relies on it).

## Verified hardware facts (from live `scratchpad/midi_monitor.py` captures)

Device sends on MIDI channel 0. Factory mapping:

| Physical control | MIDI it sends | Range |
|---|---|---|
| Joystick left/right | `pitchwheel` | −8192 … +8191, spring-centre 0 |
| Joystick up/down | `control_change` CC **1** | 0 … 127, spring-centre 64 |
| Knob 1 | `control_change` CC **1** | 0 … 127 — **same CC as joystick Y** |
| Knobs 2–8 | `control_change` CC **2–8** | 0 … 127 |
| Pads (NOTE mode, **Bank A**) | `note_on`/`note_off` **36–43** | velocity-sensitive |
| Pads (NOTE mode, **Bank B**) | `note_on`/`note_off` **44–51** | velocity-sensitive |
| Keybed (default octave) | `note_on`/`note_off` **48–72** (25 keys, C3–C5) | velocity-sensitive |
| Function buttons: ARP, TAP TEMPO, OCT▼, OCT▲, FULL LEVEL, NOTE REPEAT, and the pad-mode buttons (BANK, CC, PROG CHANGE, PROG SELECT) | **nothing** — local device functions only | — |

Consequences:

1. **Knob 1 is not independently usable** — its CC1 is the joystick Y
   axis. Accepted: CC1 is treated as `joystick_y` only; knob 1 mirrors it
   in the UI and cannot be configured.
2. **Pads must be kept on Bank A.** Bank A pad notes (36–43) do not
   overlap the keybed (48–72). Bank B pad notes (44–51) overlap the
   keybed's bottom four keys (48–51) and are indistinguishable from them
   on the same channel, so Bank B cannot be made to work cleanly. The app
   assumes Bank A and shows a transient hint if it detects Bank B.
3. **Function buttons cannot be bound** — they transmit no MIDI. Their UI
   widgets become decorative + explain this on interaction.
4. The pad-mode buttons (CC / PROG CHANGE / PROG SELECT) silently change
   what the pads transmit (NOTE ↔ CC ↔ PROGRAM). Out of scope to detect;
   the user keeps pads in NOTE mode.

## Assumptions

- The user does not use the OCT▼/OCT▲ buttons, so the keybed stays at its
  default octave (notes 48–72). Notes outside that range are dropped (see
  translator changes). Documented limitation, not handled.
- The user sets the pads to NOTE mode / Bank A once (persists in device
  memory).

## Final signal → control mapping

Implemented entirely in `midi/translator.py`'s `translate()`:

| MIDI message | `ControlEvent` |
|---|---|
| `pitchwheel` p | `joystick_x`, continuous, `p / 8192` clamped −1…1 |
| `control_change` CC 1, v | `joystick_y`, continuous, `(v − 64) / 64` clamped −1…1 |
| `control_change` CC 2–8, v | `knob_2` … `knob_8`, continuous, `v / 127` |
| `note_on` (vel > 0) note 36–43 | `pad_1` … `pad_8`, trigger |
| `note_on` (vel > 0) note 48–72 | `key_0` … `key_24`, trigger (`note − 48`) |
| `note_on` (vel > 0) note 44–47 | **no event**, but flags "Bank B seen" (see below) |
| anything else | `None` |

`note_off` / `note_on` vel 0 continue to produce no event (triggers only).

### translator.py changes

- Add module constants: `KEYBED_BASE_NOTE = 48`, `NUM_KEYS = 25`
  (import the existing `NUM_KEYS` from `ui/keybed.py` is wrong — keep MIDI
  layer self-contained; define its own or share a `core` constant. Plan
  step decides; do not create a UI→midi import).
- Keybed branch: `if KEYBED_BASE_NOTE <= note < KEYBED_BASE_NOTE + NUM_KEYS:
  return ControlEvent(f"key_{note - KEYBED_BASE_NOTE}", "trigger")`.
  Notes below 48 or above 72 that are not pad notes → `None` (drop),
  replacing today's `key_{note}` fallthrough.
- Pad branch unchanged (`PAD_NOTE_TO_CONTROL`, notes 36–43).
- Remove the dead `1: "knob_1"` entry from `KNOB_CC_TO_CONTROL` (CC1 is
  intercepted as `joystick_y` before that lookup — this is cosmetic, keeps
  the table honest). `KNOB_CC_TO_CONTROL` becomes CC 2–8 → `knob_2`…`knob_8`.
- **Bank B detection:** `translate()` stays a pure function returning
  `Optional[ControlEvent]`. Add a separate pure predicate
  `is_bank_b_pad_note(message) -> bool` (true for `note_on` vel>0 on
  44–47). `MPKController._on_message` calls it and, on true, notifies the
  UI via a new optional `on_bank_b_pad(callable)` hook passed to the
  controller (same pattern as the engine's `on_continuous`). Rationale for
  44–47 only: those four notes are sent by nothing else at the default
  octave, so a hit is an unambiguous "pads are on Bank B" signal; 48–51
  are deliberately not used as the trigger because they are also keybed
  keys.

## ActionEngine changes (`core/action_engine.py`)

Add pass/fail reporting for triggers:

- `__init__` gains `on_trigger: Optional[Callable[[str, bool], None]] = None`.
- `trigger(control)` wraps the `handler(binding.params)` call in
  `try/except Exception`; logs the exception (as `_on_message` does today)
  and calls `on_trigger(control, ok)` with `ok=False` on exception,
  `ok=True` on clean return. `switch_bank` dispatch counts as `ok=True`.
  No-binding / no-handler cases: **do not** call `on_trigger` (nothing ran,
  nothing to flash).
- `trigger()` still returns `None` (callers unchanged); the callback is the
  only new surface.
- `set_continuous` is unchanged (continuous mirroring already works via
  `on_continuous` from sub-project C).

Handlers in `core/handlers.py` keep raising on failure — the engine now
catches. No handler signature change.

## UI changes

### `ui/expanded_view.py`

1. **Function buttons decorative.** `LEFT_BUTTONS` + `RIGHT_BUTTONS` (10
   widgets: `arp_on_off`, `tap_tempo`, `octave_down`, `octave_up`,
   `full_level`, `note_repeat`, `bank_ab`, `cc`, `prog_change`,
   `prog_select`). These are `PadButton` instances today wired to
   `control_activated` / `control_configure_requested`.
   - Stop connecting their `activated` / `configure_requested` signals.
   - Render them at reduced opacity / muted style so they read as
     "present but inactive" (keep the labels — they are a visual map of
     the physical device).
   - On double-click, show a short modal/inline note: *"이 버튼은 MIDI를
     전송하지 않아 기능을 설정할 수 없습니다."* (Simplest: give them a
     dedicated tiny signal `decorative_button_activated(str)` that
     MainWindow turns into a `QMessageBox.information`, or handle entirely
     inside the widget. Plan step decides; keep it one message, no dialog
     chrome beyond `QMessageBox`.)

2. **Knob 1 widget mirrors joystick Y.** `KnobWidget` for `knob_1`:
   - `MainWindow`'s continuous mirror already routes `knob_*` values;
     additionally route `joystick_y` value into `knob_1`'s `set_value`
     (remap −1…1 → 0…1 for the dial).
   - Double-click on `knob_1` must not open `ActionConfigDialog`. It shows:
     *"1번 노브는 조이스틱 Y축과 같은 신호(CC1)라서 따로 설정할 수 없습니다."*
   - Other knobs (2–8) keep normal configure-on-double-click.

3. **Trigger flash.** Pads (`PadButton` reused from `mini_view.py`) and
   keys (`_DebouncedKey`) get a brief coloured flash driven by
   `on_trigger`: green on success, red on failure. ~150–250 ms, then
   revert. Implement as a method on each widget (`flash(ok: bool)`) using a
   `QTimer` one-shot to clear, matching the existing press-glow style on
   `PadButton`. `_DebouncedKey` needs the same `flash()` added.

4. **Bank B hint banner.** A `MainWindow`-level transient overlay (reuse
   the overlay-widget pattern from `MidiStatusDot` / `BankIndicator`):
   *"패드가 Bank B로 설정되어 있습니다 — 기기의 BANK 버튼으로 Bank A로
   전환하세요."* Appears when `on_bank_b_pad` fires, auto-hides after ~4 s,
   re-arms if it fires again after hiding. Not persistent, not blocking.

### `ui/mini_view.py`

- MiniView only shows the 8 pads. Add the same `flash(ok)` call path so
  pad triggers flash in Mini mode too (the `on_trigger` callback fans out
  to whichever view is visible, same as `update_bindings` does).
- No function buttons in Mini mode — nothing else changes.

### `ui/main_window.py`

- Pass `on_trigger=self._on_trigger` into `build_action_engine`.
- `_on_trigger(control, ok)` → look up the widget for `control` in the
  visible view, call `flash(ok)`.
- Pass `on_bank_b_pad=self._on_bank_b_pad` into `MPKController` (new
  constructor kwarg) → show the banner.
- Route `joystick_y` continuous value into the `knob_1` widget in addition
  to the joystick widget (extend `_apply_joystick_continuous`).

### `midi/mpk_controller.py`

- `__init__` gains `on_bank_b_pad: Optional[Callable[[], None]] = None`.
- `_on_message`: after `translate()`, also call `is_bank_b_pad_note(message)`
  and fire `on_bank_b_pad` if true. Keep the existing try/except wrapper.
- Nothing about connection handling changes (already resilient as of
  `db8b8d1`).

## Out of scope — added to ROADMAP as later rounds, NOT built here

- Per-bank vs. inherited/global bindings ("keep a control's function
  across banks")
- Function-label display modes (text / abbreviated / icon) per control type
- Hover tooltips describing the bound action
- Pad icon design (app-icon extraction, sticker/monochrome styles)
- Chord input (multiple keys held simultaneously → one action)
- Knob → volume / brightness defaults (sub-project D)
- Knob mouse-wheel control (sub-project E)

## Testing

Per project policy (`CLAUDE.md`): pure logic gets pytest, Qt widgets get
off-screen smoke scripts + user live verification.

- **pytest:**
  - `translate()`: note 48–72 → `key_0`–`key_24`; note 47 and note 73 →
    `None`; note 36–43 → pads unchanged; CC1 → `joystick_y`; CC2–8 →
    `knob_2`–`knob_8`; CC1 no longer yields `knob_1`.
  - `is_bank_b_pad_note()`: true for note_on 44–47 vel>0; false for
    note_off, vel 0, notes 36–43, 48–51, CC.
  - `ActionEngine.trigger`: `on_trigger(control, True)` on clean handler;
    `on_trigger(control, False)` + logged exception on raising handler;
    `on_trigger` **not** called when unbound or no handler; `switch_bank`
    path reports `True`.
  - `MPKController._on_message`: fires `on_bank_b_pad` for a 44–47
    note_on, does not for a 48 note_on.
- **Off-screen smoke:** `knob_1` double-click shows the note and does not
  open `ActionConfigDialog`; a function button double-click shows its
  note; `flash(True)`/`flash(False)` sets then clears the widget style;
  banner shows then auto-hides.
- **User live (hardware):** every pad / key / knob 2–8 / joystick axis
  drives its widget and fires its binding; function buttons are visibly
  inert; a deliberately-failing binding flashes red; switching the device
  to Bank B raises the hint.

## Risks

- The keybed-range drop (notes <48 / >72 → `None`) silently eats input if
  the user ever octave-shifts. Mitigation: it is documented, and the
  function buttons (incl. OCT) are visibly inert so the user is unlikely
  to press them. A future round could track octave from a first-seen
  offset.
- `on_trigger` flashing on every hardware pad hit adds a Qt repaint per
  trigger. Negligible (triggers are user-paced), but the flash timer must
  be a single reused `QTimer` per widget, not a new object per press.
- The Bank B banner could annoy if a stray 44–47 arrives (e.g. user
  briefly on Bank B on purpose). Auto-hide + non-blocking keeps it cheap;
  acceptable.
