# Natural-Language Action Configuration — Design

## Goal

Let the user describe a pad/knob binding in plain language (Korean or
English) instead of manually picking an action type and typing/browsing a
path — e.g. typing "카카오톡 열어줘" should produce the same result as
manually choosing `launch_program` + picking KakaoTalk from the installed-
program list.

## Context / decision already made

`mpk-deck`'s original design (`mpk-deck/CLAUDE.md`) stated no AI/LLM calls
belong in this repo. The user explicitly overrode that for this feature —
see `ROADMAP.md`'s Core Architectural Principle (updated 2026-08-19): the
AI/execution separation applies to *risk-sensitive domains*, not
universally. This feature is not risk-sensitive (it only ever fills a form
the user reviews before saving — see below), so it doesn't violate even the
original spirit of that principle. This decision is not open for
re-litigation in this spec.

## Non-goals

- No auto-save / auto-execute from an NL description. The LLM only ever
  proposes a `Binding`; the existing dialog fields show the proposal and the
  user must still click Save.
- No conversational back-and-forth, no multi-turn clarification UI. One
  shot: type a description, get a proposal (or an inline error).
- No provider abstraction layer (single Claude client, hardcoded). Revisit
  only if a second provider is actually needed later.

## Architecture

```text
ActionConfigDialog (existing)
  +-- "Describe what you want" QLineEdit + "Generate" QPushButton   [new]
  +-- (existing) action-type list + per-action param pages
        |
        v (Generate clicked)
  core/nl_action.py: parse_nl_action(text, installed_programs, client=None)
        |
        v
  Anthropic API (Claude Haiku 4.5, tool-use / forced JSON schema)
        |
        v
  Binding | None  -->  fills the existing action list selection + param
                       fields (same code path as loading an `existing`
                       binding today) -- or shows an inline error label
```

- **New module**: `src/mpk_deck/core/nl_action.py`
  - `parse_nl_action(text: str, installed_programs: list[InstalledProgram], *, client=None) -> Binding | None`
  - `client` is injectable (same pattern as `handlers.py`'s `finder`/
    `volume_setter`, `program_finder.py`'s `resolver`) so tests don't need a
    real API key or network call.
  - Internally: builds a short prompt containing (a) the 4 known action
    types + their param shapes, (b) the installed-program list (name only,
    not full paths — the model picks a name, we resolve the path
    server-side from the already-known list, never trust a path the model
    invents), (c) the user's text. Uses Anthropic's tool-use feature with a
    single forced tool (`propose_binding`) whose input schema mirrors
    `Binding` (`action`, and the one relevant param key for that action) so
    the response is always structured, never freeform text to parse.
  - Validates the tool-call output before returning: `action` must be one
    of the 4 known names; for `launch_program`, the chosen program name
    must exactly match one from `installed_programs` (else return `None` —
    never fabricate a path); for `open_url`, do a minimal sanity check
    (starts with `http://`/`https://`, else prefix `https://`); for
    `focus_window`/`set_system_volume`, pass through with the existing
    `PARAM_KEY` shape.
  - Any API/network error, missing key, or failed validation -> returns
    `None`. Caller (the dialog) shows one inline error label; never raises
    out to crash the UI.

- **API key**: `ANTHROPIC_API_KEY` read from environment via
  `python-dotenv`'s `load_dotenv()` at app startup (in `__main__.py`) +
  `os.environ`. Loaded once, not per-call. `.env` is already gitignored (no
  `.gitignore` change needed). No in-app key entry UI — if the key is
  missing, `parse_nl_action` returns `None` immediately (checked before
  attempting a network call) and the dialog shows "ANTHROPIC_API_KEY not
  set" as the inline error, pointing at `.env`.

- **New dependencies** (`pyproject.toml`): `anthropic`, `python-dotenv`.

- **`ActionConfigDialog` change**: one `QLineEdit` (placeholder: "or
  describe what you want...") + one `QPushButton` ("Generate") added above
  the existing action list/param area. On click: disable the button, call
  `parse_nl_action` (blocking call is acceptable here — a config dialog the
  user just opened, a few hundred ms to a couple seconds of wait is fine
  for a personal tool; no need for async/threading machinery), re-enable
  the button, and either (a) call the existing `_select_action()` +
  populate the relevant param field with the returned `Binding`'s data, or
  (b) show an inline `QLabel` error below the input, styled with the
  existing dialog's error-adjacent color (reuse `DIALOG_QSS`, add one
  `QLabel#nlError { color: #ff6b6b; }` rule).

## Testing

- `parse_nl_action`: pytest with a fake/mock `client` object (mimicking the
  Anthropic SDK's tool-use response shape) covering: valid launch_program
  match, model picks a program not in the installed list (rejected ->
  `None`), model returns an unknown action name (rejected -> `None`),
  open_url without a scheme (gets `https://` prefixed), missing API key
  (returns `None` without attempting a call — assert the fake client's
  `.messages.create` was never invoked).
- Dialog wiring (button click -> fields populate / error shows): manually
  verified like the rest of the dialog UI (no existing pytest coverage
  for `ActionConfigDialog`, consistent with project convention).
- Real API call against the live Anthropic API: manually verified once by
  the user with a real `.env` key in place, exercising a few Korean and
  English phrasings across all 4 action types.

## Error handling / safety

- The LLM never executes anything and never receives write access to
  anything — it only ever returns a proposed `(action, param)` pair that
  flows through the exact same `Binding` construction, `action_registry`
  validation, and `save_bindings()` path a manual dialog edit already uses.
- `launch_program` grounding against the real installed-program list (never
  a model-invented path) is the one safety-relevant piece of this feature;
  it's covered explicitly by the tests above.
- No prompt injection surface of consequence: the model's only "action" is
  producing a small structured payload the user visually reviews before
  Save; there's no path from the NL text to code execution or to writing
  files other than what the user manually confirms.
