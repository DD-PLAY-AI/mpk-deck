# Bank/profile system — design

Sub-project B of the "everyday deck" round (see `mpk-deck/CLAUDE.md`'s
"다음 라운드" section, `ROADMAP.md`'s 2026-08-25 Decision Log). Foundational —
sub-projects C/D/E build on this.

## Problem

`config/actions.yaml` holds one flat `control -> Binding` map, loaded once
into `ActionEngine` at startup. The user wants many independently-named
sets of bindings ("banks" — not just the hardware's literal Bank A/B),
switchable at runtime from any control (not just the keybed), with the
active bank's bindings shown identically in both `MiniView` and
`ExpandedView`.

## Data model

`config/actions.yaml`'s schema changes from a flat list to:

```yaml
active_bank: bank_a
switch_bindings:      # global — applies no matter which bank is active
  key_0: bank_a
banks:
  bank_a:
    name: "Home"
    bindings:
      - control: pad_1
        type: trigger
        action: launch_program
        params: {path: ...}
  bank_b:
    name: "Trading"
    bindings: [...]
```

- `banks.<id>.bindings` uses the exact same `Binding` list format as
  today — no change to `Binding` itself.
- `switch_bindings` is a flat `control -> bank_id` map, separate from any
  bank's own `bindings` list. A control listed here always switches banks,
  regardless of which bank is currently active — it is never looked up in
  a bank's own binding list.
- `bank_a` always exists (the app ships with it) and is the default
  `active_bank` on first run. `key_0` (the keybed's leftmost key) is
  fixed to `switch_bindings: {key_0: bank_a}` by default — always
  present, not user-removable through the UI (see Locking below).
- `active_bank` persists in the same YAML file and is updated (and the
  file re-saved) every time a real `switch_bank` fires, so the app
  reopens on whichever bank was active when it last closed — same
  "remember last state" pattern as `config.py`'s `load_last_mode`/
  `load_last_theme`, just stored in `actions.yaml` instead of `QSettings`
  since it's part of the binding configuration's own state, not a UI
  preference.

### Migration

Any `actions.yaml` written before this change uses the old flat
`bindings: [...]` format (no `banks`/`switch_bindings`/`active_bank`
keys). `action_registry.load_bindings` (or a new sibling function) detects
this shape and migrates it in memory: wraps the existing bindings into
`banks: {bank_a: {name: "Home", bindings: [...]}}`, adds
`switch_bindings: {key_0: bank_a}`, sets `active_bank: bank_a`. The next
save (from any dialog Save, or the first real bank switch) writes the
file back out in the new format. No destructive rewrite happens just from
loading — only on the next actual save, consistent with the existing
"config file is the source of truth, GUI/engine round-trip through the
same load/save functions" pattern.

A missing `actions.yaml` (fresh install, today's existing
`build_action_engine`'s except-branch case) seeds the same default state
the migration path produces from an empty binding list: `banks: {bank_a:
{name: "Home", bindings: []}}`, `switch_bindings: {key_0: bank_a}`,
`active_bank: bank_a`.

## `ActionEngine`

Stays a plain Python class (no Qt dependency, matching its current
design). Changes:

- Replaces `load_bindings(bindings: list[Binding])` with
  `load_banks(banks: dict[str, list[Binding]], switch_bindings: dict[str, str], active_bank: str)`.
  Internally builds `_bindings_by_control` from `banks[active_bank]` plus
  a synthetic `switch_bank` `Binding` for each entry in
  `switch_bindings` (so `trigger()`'s existing control->Binding lookup
  keeps working unmodified for switch controls).
- New `switch_bank(bank_id: str) -> None`: swaps `_bindings_by_control`
  to `banks[bank_id]` (re-merged with the same global switch bindings),
  updates `active_bank`, calls `on_bank_changed(bank_id)` if one was
  provided.
- New constructor parameter `on_bank_changed: Callable[[str], None] | None = None`
  — plain callback injection, same style as `handlers.py`'s
  `finder=`/`volume_setter=` pattern, not a Qt signal (keeps the engine
  Qt-free).
- `trigger()` special-cases `binding.action == "switch_bank"`: instead of
  looking up a registered handler (there isn't one — `switch_bank` is
  never added to `handlers.py`), it calls `self.switch_bank(binding.params["bank_id"])`
  directly. This is a deliberate, narrow exception to "actions always go
  through a registered handler" — `switch_bank` mutates the engine's own
  state, it isn't a device action, so it doesn't belong in `handlers.py`
  alongside `launch_program`/`open_url`/etc.

## `ActionConfigDialog` — "Add Bank" flow

- `ACTION_CHOICES` gains one entry: `("switch_bank", "➕", "Add Bank")`.
- Its param page: a single text field, "Bank name". No target-bank
  picker — this flow only ever *creates* a new bank, it never lets you
  point a control at an existing one (deliberately out of scope, see
  below).
- On Save with `switch_bank` selected on a previously-unbound (or
  differently-bound) control: generate a bank id (slugify the name —
  lowercase, non-alphanumerics to `_`, de-duplicated with a numeric
  suffix on collision), create the bank (empty `bindings: []`), add
  `switch_bindings[control] = new_id`, save. `bank_a`'s id is always the
  literal string `bank_a`, never generated this way (it's seeded at
  first run, not through this flow).
- **Locking**: opening the dialog for a control that's already in
  `switch_bindings` shows only the Add Bank entry as selectable — every
  other `ACTION_CHOICES` item is disabled (`Qt.ItemIsEnabled` cleared) —
  and the name field is pre-filled with the target bank's current name;
  editing it and saving renames that bank. The control can never be
  reassigned to a different action or a different target bank through
  this dialog. This applies to `key_0` from first run too (it's already
  in `switch_bindings` by default).

## Bank name indicator

New `ui/bank_indicator.py`, same shape as `ui/midi_status_dot.py`
(sub-project A): a small `QLabel`-based widget showing the active bank's
display name, theme-aware text color (light/dark, matching whichever
palette `MiniView`/`ExpandedView` currently use), instantiated once in
`MainWindow` as a floating overlay positioned next to the existing
`MidiStatusDot` (both bottom-right corner) — so it's automatically
identical in Mini and Expanded mode, same reasoning as A's dot placement.
`MainWindow` updates its text whenever `ActionEngine`'s `on_bank_changed`
callback fires, and once at startup.

## `MainWindow` wiring

- `build_action_engine()` (or a new equivalent) loads banks via
  `action_registry`'s new bank-aware load function, calls
  `engine.load_banks(...)`, passes `on_bank_changed=self._on_bank_changed`.
- `_on_bank_changed(bank_id)`: re-reads `engine.bindings` into
  `self._bindings`, calls `self._mini_view.update_bindings(...)` (same
  as after a dialog Save today), updates the bank indicator's text,
  triggers a save of `active_bank` back to `actions.yaml`.
- `_on_control_configure_requested` needs the list of existing banks
  (for nothing beyond knowing whether a control is already in
  `switch_bindings` — the dialog itself doesn't need to enumerate other
  banks, since Add Bank never targets an existing one).

## Out of scope for this sub-project

- Retargeting an existing switch-bank control to a *different* existing
  bank (Add Bank only creates new banks).
- Deleting a bank or removing a `switch_bindings` entry.
- Any UI inside `ExpandedView` reflecting per-control bound-action icons
  (that's `MiniView`-only today via `update_bindings`, unchanged here).
- Binding `switch_bank` to knobs — it's a trigger-type action like
  `launch_program`; knobs only ever receive continuous values, so a
  knob bound to it would simply never fire, same as today's existing
  (unenforced) mismatch between trigger-only actions and knob controls.

## Testing

- `action_registry`: new/updated pure-function tests for the bank-aware
  YAML shape (parse, round-trip save, and the old-format migration path).
- `action_engine`: `load_banks`/`switch_bank`/`trigger`-dispatches-to-
  switch_bank tests, following the existing `ActionEngine` test style
  (plain Python, no Qt).
- `ActionConfigDialog`'s Add Bank flow and the locking behavior are Qt
  widget code — per project policy, not pytest-covered; verified manually
  (or via an off-screen smoke script) same as `ExpandedView`/`MainWindow`.
