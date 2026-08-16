# mpk-deck Phase 1 MVP — Design Spec

Date: 2026-08-17

## Overview

Phase 1 MVP for `mpk-deck`: a software Stream Deck combining an Action
Engine, a PySide6 Personal Deck UI (Mini + Expanded modes), and AKAI MPK
mini MK2 MIDI integration. No AI, no StackChan, no multi-monitor — those
are later phases (see `ROADMAP.md`).

## Scope

**In scope (Phase 1):**
- Action Engine (central dispatcher, trigger + continuous actions)
- Personal Deck UI — Mini mode (8 pads) and Expanded mode (full MPK mini
  MK2 replica)
- MPK mini MK2 MIDI input (event-driven, pads/keys/knobs/joystick/buttons)
- Trigger actions: launch program, open URL, basic window control
- Continuous actions: knob → system volume (Windows, via `pycaw`)
- `actions.yaml` as the source of truth for bindings, editable by hand or
  via an in-app GUI dialog

**Explicitly out of scope (later phases / other repos):**
- Natural-language action editing — belongs in `ai-hub` once it exists.
  `ai-hub` will parse natural language into structured intents and write
  to this repo's `actions.yaml` via a local protocol (TBD) rather than
  `mpk-deck` calling any LLM itself. Keeps the AI/execution boundary from
  `ROADMAP.md` intact.
- Monitor Manager, multi-monitor placement, Workspace Profiles (Phase 2)
- StackChan, KakaoTalk, cloud — later phases / other repos

## Tech Stack

- Python 3.13
- PySide6 (UI)
- `mido` + `python-rtmidi` (MIDI input, event-driven callbacks — no polling)
- `PyYAML` (`actions.yaml`)
- `pycaw` (Windows system volume control, for knob continuous actions)
- `pytest` (Action Engine unit tests)

## Architecture

```
MPK mini MK2 (MIDI) ──┐
                       ├──> Action Engine ──> trigger_action(id) / set_continuous(id, value)
Deck UI click/drag ────┘         │
                                  ├──> registered trigger actions (program/url/window)
                                  └──> registered continuous actions (volume, etc.)
```

- Action Engine is the single entry point. MIDI callbacks and UI clicks
  both call into it — neither path executes anything directly.
- Two binding kinds:
  - **Trigger actions** (pads, keys, buttons): fire once per press.
  - **Continuous actions** (knobs, joystick axes): receive a normalized
    value on every MIDI CC update and apply it continuously (e.g. volume).
- `actions.yaml` is the source of truth. A right-click-to-configure GUI
  dialog (pick action type from a dropdown, fill in a parameter — file
  picker for programs, text field for URLs) edits it; hand-editing the
  YAML directly also works.

## Package Structure

```
mpk-deck/
├── src/mpk_deck/
│   ├── core/
│   │   ├── action_engine.py      # dispatch: trigger_action(), set_continuous()
│   │   └── action_registry.py    # loads/validates actions.yaml
│   ├── midi/
│   │   └── mpk_controller.py     # mido/rtmidi listener -> Action Engine calls
│   ├── ui/
│   │   ├── main_window.py        # Mini/Expanded mode toggle, QSettings persistence
│   │   ├── mini_view.py          # 8-pad glass widget
│   │   ├── expanded_view.py      # full MPK mini MK2 replica (see layout below)
│   │   └── action_config_dialog.py
│   └── config.py
├── config/actions.yaml
├── tests/
└── pyproject.toml
```

## UI Design

**Theme:** Glassmorphism — translucent blur, rounded corners, soft shadow.
Light (vibrant purple/blue gradient) is default; a dark variant (matches
the physical black-on-black MPK unit) is user-toggleable and persisted.

**Mini mode:** compact widget, 8 pads in a 2×4 grid, matching the MPK's
physical PAD1-4 (bottom row) / PAD5-8 (top row) numbering.

**Expanded mode:** full replica of the physical MPK mini MK2 layout so
every control (joystick, 6 left-side buttons, 8 pads, 8 knobs, 4
pad-control buttons, 25-key keybed) is visible and clickable to open the
action-config dialog for that control.

### Expanded mode layout (measured from the physical unit, panel aspect-ratio 312:184)

All coordinates are `%` of the panel box (`position:relative`, width ×
`184/312` height). Buttons are pixel-fixed so every button on the device
renders at the identical size regardless of label length.

| Element | left | top | width | height | notes |
|---|---|---|---|---|---|
| Left column (joystick + 6 buttons) | 3% | 4% | content-fit | content-fit | joystick 40px circle, 3 rows of 2× 34×16px buttons, 5px gaps, centered |
| Pad grid (2×4) | 18% | 2% | 42% | 36% | row 1 = PAD5-8, row 2 = PAD1-4, 5% gap |
| Knob grid (2×4) | 63% | 4% | 34% | content-fit | 24px dials, 14px row-gap |
| Pad-controls row | 63% | 32% | content-fit | content-fit | BANK A/B + CC + PROG CHG grouped (bordered, `width:fit-content`, 2% left margin outside the border), PROG SEL 24px gap to its left |
| Keybed | 1.5% | 44% | 97% | 54.5% | 15 white + 10 black keys (C→C, 2 octaves + 1), ~1.5% margin on all sides |

All 10 physical buttons (ON/OFF, TAP TEMPO, OCT▼, OCT▲, FULL LEVEL, NOTE
REPEAT, BANK A/B, CC, PROG CHANGE, PROG SELECT) render at a fixed
34×16px — `overflow:hidden` + `box-sizing:border-box` on the button class
to stop flex's default min-width:auto from letting long labels
(e.g. "NOTE REPEAT") grow the box.

## Action Configuration

`actions.yaml` example:

```yaml
bindings:
  - control: pad_1
    type: trigger
    action: launch_program
    params: { path: "C:/Users/.../VSCode.exe" }
  - control: pad_2
    type: trigger
    action: open_url
    params: { url: "https://github.com/DD-PLAY-AI" }
  - control: knob_1
    type: continuous
    action: set_system_volume
```

GUI dialog (opened by clicking a control in Expanded mode, or a pad in
Mini mode) lets the user pick an action type and fill in params without
hand-editing YAML; it writes back to the same file.

## Testing

- `pytest` covers Action Engine registry/dispatch logic in isolation
  (no Qt, no MIDI hardware required).
- MIDI input and UI rendering are verified manually (hardware-dependent).

## Error Handling

- MPK not connected: UI shows "MPK not detected", falls back to
  click-only operation — no crash.
- Invalid/missing action in `actions.yaml`: log and skip that binding;
  app keeps running.

## Decision Log

See `ROADMAP.md` Decision Log for the repo-split decisions. This spec's
own key decisions (2026-08-17):
- Natural-language action editing deliberately kept out of `mpk-deck` —
  belongs in `ai-hub` to preserve the AI/execution boundary.
- Knob continuous actions (starting with system volume) pulled into
  Phase 1 scope at the user's request, ahead of the original "Future"
  placement in the source spec.
- Expanded-mode layout coordinates were measured directly from a photo
  of the user's physical unit (grid-overlay technique) rather than
  guessed, after several rounds of visual iteration.
