# Joystick scroll + visual movement — design

Sub-project C of the "everyday deck" round (see `mpk-deck/CLAUDE.md`'s
"다음 라운드" section, `ROADMAP.md`'s 2026-08-25 Decision Log). Builds on
B (bank/profile system) — joystick bindings live inside each bank's
`bindings` list like any other control.

## Problem

`ExpandedView`'s joystick is currently a plain `PadButton` labeled "JOY" —
click-to-trigger / double-click-to-configure, same as a pad. It has no
continuous behavior and doesn't visually move. The user wants: (1) the
physical MPK's joystick, by default, scrolls whatever window they're
actually working in (horizontal on X, vertical on Y), with a light push
scrolling slowly and a full push scrolling fast; (2) the `ExpandedView`
joystick widget visually mirrors that deflection; (3) scroll sensitivity
is user-configurable per axis.

Real hardware wiring (plugging in and confirming live) was originally
slated for sub-project F, but the user wants the UI to react to hardware
input as part of this round, so this spec pulls the `midi/translator.py`
side of that forward. What stays deferred to live-testing (not blocking
this spec or its implementation) is documented under **Open questions**
below — it's a hardware fact, not a design decision.

## Two independent input paths, one visual widget

Early in design, mouse-drag-to-scroll (drag the on-screen joystick with
the mouse to actually scroll) was considered and dropped: the cursor
would be sitting on `ExpandedView` itself while dragging, and Windows
routes real wheel-input by cursor position (not focused window), so a
real `SendInput` wheel event would scroll mpk-deck's own window, not the
app the user is actually working in. Faking it with `PostMessage` to a
specific window avoids that but is unreliable — many apps (Chrome/
Electron especially) ignore synthetic, non-injected wheel messages.

The user's real workflow only ever drives scroll from the physical
joystick — the mouse cursor stays wherever they're actually working, so a
real `SendInput` wheel event lands correctly with no extra plumbing. Mouse
drag on the on-screen widget is kept only as a **visual preview** — moving
the handle so the user can see the widget works — with no scroll side
effect. Two input paths update the same visual state; only one of them
also drives the engine:

```
hardware (pitchwheel/CC) -> translator -> engine.set_continuous()
                                              |
                                              +--> scroll_horizontal/vertical handler (real SendInput)
                                              +--> on_continuous callback -> JoystickWidget.set_deflection() [visual]

mouse drag on JoystickWidget -> JoystickWidget's own handle position [visual only, no engine call]
```

## `midi/translator.py`

Two additions to `translate()`:

- `message.type == "pitchwheel"` -> `ControlEvent(control="joystick_x", kind="continuous", value=normalized)`,
  where `normalized = max(-1.0, min(1.0, message.pitch / 8192))` (`mido`'s
  pitchwheel range is -8192..8191, 0 = center).
- `message.type == "control_change"` and `message.control == JOYSTICK_Y_CC`
  (new constant, `JOYSTICK_Y_CC = 1`, same tentative CC `mpk-deck/CLAUDE.md`
  already suspected for the joystick's Y axis — see Open Questions) ->
  `ControlEvent(control="joystick_y", kind="continuous", value=normalized)`,
  where `normalized = max(-1.0, min(1.0, (message.value - 64) / 64))` (CC
  is 0..127, 64 = assumed center).
- This check runs **before** `KNOB_CC_TO_CONTROL`, not after: CC1 is also
  `KNOB_CC_TO_CONTROL`'s existing entry for `knob_1`, and this round's
  purpose is making the joystick work, not preserving `knob_1`. If the two
  really do collide on the real device, `knob_1` becomes unreachable via
  CC1 until a live test resolves it (shift `KNOB_CC_TO_CONTROL` to start
  at CC2, or move `JOYSTICK_Y_CC` to whatever the real number turns out to
  be) — a one-line constant change either way, not a redesign. This is the
  same known risk `mpk-deck/CLAUDE.md` already flagged before this
  sub-project started, just now resolved in the joystick's favor by
  default instead of left unresolved.

Both new `ControlEvent`s are `kind="continuous"`, value range -1.0..1.0 —
deliberately different from knobs' existing 0.0..1.0 (a knob's value is an
absolute dial position; a joystick's is a bipolar deflection from center).
`ActionEngine.set_continuous` and the `ContinuousHandler` signature don't
care about a handler's value range, so this needs no engine change beyond
the addition below.

## `core/action_engine.py`

New constructor parameter `on_continuous: Callable[[str, float], None] | None = None`
— same plain-callback-injection style as `on_bank_changed`. `set_continuous()`
calls it (if provided) with `(control, value)` right after invoking the
registered handler, regardless of which control fired. This is the engine's
only new surface: it stays value-range-agnostic and Qt-free.

## `core/handlers.py`

```python
def scroll_horizontal(params: dict, value: float, *, sender=None) -> None:
    """`value` in [-1.0, 1.0]: joystick X deflection, 0 = centered/no scroll.
    `params.sensitivity` (float, default 1.0) scales the notch count."""
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
    """Pure: deflection + sensitivity -> whole wheel notches for one call.
    Linear in |value| so a light push scrolls slowly and a full push scrolls
    fast; sign gives direction. No Qt/win32 - pytest-covered directly."""
    return round(max(-1.0, min(1.0, value)) * sensitivity * max_notches)


def _default_scroll_sender(*, horizontal: bool, notches: int) -> None:
    """Real SendInput wheel injection - same class of input as a physical mouse
    wheel, so it works in every app (unlike PostMessage). Lands on whatever
    window the OS cursor is actually over, which in real use is always the
    app the user is working in (see design doc: mouse-drag-to-scroll was
    deliberately dropped so this cursor position is never mpk-deck itself)."""
    import win32api
    import win32con

    flag = win32con.MOUSEEVENTF_HWHEEL if horizontal else win32con.MOUSEEVENTF_WHEEL
    win32api.mouse_event(flag, 0, 0, notches * 120, 0)  # WHEEL_DELTA = 120/notch
```

`sender` is injectable exactly like `focus_window`'s `finder` and
`set_system_volume`'s `volume_setter` — tests pass a fake and assert
`(horizontal, notches)` without touching `win32api`.

## Repeat-while-held timer (`ui/main_window.py`)

MIDI only sends a message when the joystick's position *changes* — a
real spring-loaded stick held at a fixed deflection won't re-send on its
own, so nothing would repeat-scroll while just held. `MainWindow` owns one
`QTimer` (50ms / 20Hz):

- Every `on_continuous(control, value)` callback for `joystick_x`/`joystick_y`
  updates `self._joystick_values[control] = value` and calls
  `self._joystick_widget.set_deflection(...)` (marshaled onto the GUI
  thread via `QTimer.singleShot(0, ...)`, same pattern used for `on_bank_changed`
  in sub-project B, since MIDI callbacks arrive on `mido`'s own thread).
- If either value is non-zero and the timer isn't running, start it. On
  each tick, re-call `self._engine.set_continuous(control, value)` for
  every control whose last known value is non-zero (drives the handler
  again, producing the "hold to keep scrolling" effect).
- If both values are ~0 (a released/centered stick reliably sends a
  centered MIDI message on spring-back), stop the timer. **No timer runs
  while idle** — satisfies the project's CPU/RAM-minimal constraint; this
  is scoped, bounded-duration polling during an active interaction, not a
  background loop.
- Mouse-drag preview updates (see below) go straight to the widget and
  never touch `self._joystick_values` or this timer — they can never
  trigger a scroll.

## `ui/joystick_geometry.py` (new, pure, pytest-covered)

```python
def clamp_deflection(dx: float, dy: float, max_radius: float) -> tuple[float, float]:
    """Clamp a raw pixel offset from center to a circle of max_radius,
    return axes normalized to [-1.0, 1.0] on each dimension."""
```

Used only by the mouse-drag preview path (below) to keep the handle
inside the widget's base circle. The hardware path already receives
pre-normalized -1..1 values from the translator and doesn't need it.

## `ui/expanded_view.py` — `JoystickWidget`

Replaces the current `PadButton("JOY", ...)`. A small `QFrame` (base
circle, matching `BASE_JOYSTICK_D`) with a child handle `QFrame` positioned
via `set_deflection(x: float, y: float)` (`x, y` in -1..1; handle center =
widget center + `(x, y) * (base_radius - handle_radius)`).

- `mousePressEvent`/`mouseMoveEvent`: compute the raw pixel offset from
  the widget's center, run it through `clamp_deflection`, call
  `set_deflection(...)` directly (no signal emitted — purely local visual
  state, never reaches `MainWindow` or the engine).
- `mouseReleaseEvent`: `set_deflection(0.0, 0.0)` (springs back, matching
  a real joystick's resting position).
- `mouseDoubleClickEvent`: opens a small two-item `QMenu` at the cursor —
  "Horizontal (joystick_x)" / "Vertical (joystick_y)" — each entry emits
  the widget's existing `configure_requested(str)`-shaped signal with the
  corresponding control id, routed through `MainWindow`'s existing
  `_on_control_configure_requested` exactly like any other control (no new
  dialog code).
- No `activated`/click-trigger signal at all — the joystick was never a
  meaningful single-click action and dropping it removes the need for
  `PadButton`'s click/double-click debounce timer here.

`MainWindow`'s hardware path calls `set_deflection` too (through the
`on_continuous` marshaling above), so both paths share one rendering
function and can never desync in intent — whichever last wrote to it wins,
which is fine since they don't fire concurrently in real use (a user
either drags the mouse preview or uses the physical hardware, not both at
once).

## `ui/action_config_dialog.py`

- `ACTION_CHOICES` gains two entries: `scroll_horizontal` ("↔️", "Scroll Horizontal"),
  `scroll_vertical` ("↕️", "Scroll Vertical"). Both `ACTION_TYPE: "continuous"`.
- New params page (`_build_sensitivity_page`): a single numeric field
  (`QLineEdit` restricted to floats, consistent with the rest of the
  dialog's plain-`QLineEdit` param pages) for `sensitivity`, default text
  `"1.0"`, used for both scroll actions.
- `_apply_binding`/`result_binding` gain a branch for
  `action in ("scroll_horizontal", "scroll_vertical")`: reads/writes
  `params={"sensitivity": float(text) or 1.0}` instead of the generic
  `PARAM_KEY` text-field path (same shape as the existing `switch_bank`
  special case, just returning a real params dict instead of `{}`).
- Nothing about locking changes — `scroll_horizontal`/`scroll_vertical`
  are ordinary continuous actions; any control (not just the joystick) can
  in principle be bound to them, same as any other registered action.

## Default bindings & migration

Every bank should scroll out of the box, matching the roadmap's
"조이스틱을 기본으로 가로/세로 스크롤 액션에 매핑". Two seeding points,
both non-destructive (write-back only on next save, same pattern B
established for the flat->banked migration):

- **New banks** (via the Add Bank flow): seeded with
  `[Binding(joystick_x, scroll_horizontal, {sensitivity: 1.0}), Binding(joystick_y, scroll_vertical, {sensitivity: 1.0})]`
  instead of B's current empty `bindings: []`.
- **Existing banks** (already-saved `actions.yaml` from before this
  change, including the user's own "ai"/"ai_2" banks and `bank_a`):
  `load_config` backfills the same two default bindings into any bank
  whose `bindings` list has no entry for `joystick_x`/`joystick_y`, in
  memory only, same non-destructive-until-next-save rule as the B
  migration. A bank that already has one (someone rebound it) is left
  alone.

## Out of scope for this sub-project

- MiniView never gets a joystick widget — it doesn't show one today and
  the roadmap only asks for `ExpandedView`'s to move.
- Non-linear sensitivity curves (e.g. exponential ramp-up) — linear
  scaling already satisfies "light push = slow, full push = fast";
  nothing in the request asks for a curve, and `_scroll_notches` can grow
  one later without touching its callers if it turns out linear feels
  wrong live.
- Deciding the real `JOYSTICK_Y_CC` value or resolving a `knob_1`
  collision if one exists — hardware fact, not buildable in software, see
  Open Questions.
- Any change to `handlers.py`'s existing trigger-only handlers or to
  `ActionEngine`'s trigger dispatch path — this sub-project only adds a
  second continuous-callback surface alongside the existing one.

## Testing

- `midi/translator.py`: pitchwheel and CC(`JOYSTICK_Y_CC`)-to-normalized-
  value tests (center, both extremes, clamping), following the existing
  `translate()` test style.
- `core/action_engine.py`: `on_continuous` fires with the right
  `(control, value)` on `set_continuous`, independent of whether a handler
  is registered for that control's bound action.
- `core/handlers.py`: `_scroll_notches` pure-function table tests (sign,
  magnitude, sensitivity scaling, rounding at the clamp boundaries);
  `scroll_horizontal`/`scroll_vertical` tests via injected `sender`
  (assert `horizontal` and `notches`, never touch `win32api`).
- `ui/joystick_geometry.py`: `clamp_deflection` pytest tests (inside the
  circle, on the boundary, outside the circle, both axes independently).
- `JoystickWidget`, the repeat timer, and `ActionConfigDialog`'s new pages
  are Qt widget code — per project policy, not pytest-covered; verified
  via an off-screen smoke script (inject synthetic mouse events and
  synthetic `on_continuous` calls, assert `set_deflection` receives the
  right values and that mouse-drag never calls `engine.set_continuous`)
  same as prior rounds.

## Open questions (resolved by live hardware testing, not by this spec)

- The real MIDI message(s) the MPK mini MK2's joystick actually sends for
  each axis — `pitchwheel` for X is a reasonable default assumption (most
  MK2-class controllers use it), but unconfirmed. `JOYSTICK_Y_CC = 1` is a
  guess carried over from the existing `mpk-deck/CLAUDE.md` note.
- Whether the joystick's Y axis and `knob_1` really do collide on the same
  CC number on this specific physical unit - if so, a follow-up one-line
  fix (shift `KNOB_CC_TO_CONTROL`'s range, or pick a different constant for
  `JOYSTICK_Y_CC`) resolves it once observed live; nothing in this design
  depends on guessing correctly ahead of time.
- Whether `SendInput`-based `MOUSEEVENTF_WHEEL`/`HWHEEL` is accepted by the
  user's actual daily apps (Chrome, KakaoTalk, etc.) at the injected notch
  granularity - expected to work (it's real synthetic hardware input, the
  same class real mice generate), but only confirmed live.
