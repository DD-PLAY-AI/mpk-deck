# mpk-deck

A lightweight Windows software Stream Deck: an Action Engine paired with a
PySide6 Personal Deck UI and AKAI MPK mini MK2 MIDI control. Physical pad
presses and UI clicks trigger the same registered actions (launch programs,
open URLs, move/resize windows, switch workspaces).

> Status: early planning / Phase 1 MVP not yet implemented.

## Scope

- **Action Engine** - central dispatcher; every input (MPK, UI, future voice/AI)
  calls into the same registered, configurable actions.
- **Personal Deck UI** - compact PySide6 widget showing configurable
  buttons/pages, reflecting and triggering the same actions as the MPK.
- **MPK MIDI integration** - event-driven MIDI input from the AKAI MPK mini
  MK2, mapped to actions via configurable profiles.
- **Windows Window Manager** - launch/find/move/resize/focus windows,
  always-on-top, restore saved layouts.
- **Monitor Manager** - detect displays and assign roles (e.g. auto-place the
  Personal Deck on a designated mini monitor when connected).
- **Workspace Profiles** - one action switches an entire environment
  (apps + window layout + monitor assignment).

## Relation to other DD-PLAY-AI projects

`mpk-deck` is the deterministic execution layer. [`ai-hub`](https://github.com/DD-PLAY-AI/ai-hub)
is expected to call into it (locally, via a documented protocol) to execute
AI-decided structured intents rather than issuing raw OS commands directly.

## Design principles

- Action Engine is the core; all input methods share the same action system.
- Event-driven, not polling (MIDI callbacks, not busy loops).
- Keep the UI idle-light: low CPU/RAM at rest.
- Build the MVP before adding complexity - AI is out of scope for this repo.

Background: this scope corresponds to sections 3-8 (Personal Deck, Action
Engine, MPK integration, Window/Monitor Manager, Workspace Profiles) of the
DD-PLAY-AI workspace planning spec.
