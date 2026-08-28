# Design preferences (accent color + knob style) — design

Ad-hoc sub-project, inserted mid-session between joystick-scroll sub-project
C's Task 8 and Task 9 (see `docs/superpowers/plans/2026-08-28-joystick-scroll.md`)
at the user's explicit request. Not part of the original A-F roadmap
ordering — grew out of a live bug report (BankIndicator unreadable in dark
mode, `JoystickWidget`'s handle rendering as a square) into a real,
persisted, user-facing settings feature during design review. Explored
interactively via an HTML comparison mockup (dark/light theme toggle, 7
accent swatches, knob-style A/B toggle, a live-draggable joystick, and a
pad-grid + keybed preview) before being written up here — every visual
token below is what the user actually approved in that mockup, not a fresh
guess.

## Problem

Three real bugs/gaps surfaced together during sub-project C's Task 6/8
work:

1. `BankIndicator`'s translucent "glass pill" (added in sub-project B) is
   unreadable in dark mode — its fill alpha (18/255) provides negligible
   contrast against the app's own dark panel, and both its text and border
   are near-white, so there's nothing for the near-white text to contrast
   against.
2. `JoystickWidget`'s handle (built in sub-project C's Task 6) renders as a
   flat blue square, not a circle — its `border-radius: 999px` QSS never
   applies because neither it nor its parent widget has
   `WA_StyledBackground` set (the exact same class of bug this project hit
   once before with `MiniView`/`ExpandedView`'s own backgrounds).
3. The 8 knobs have no visual indicator of their current value at all —
   just a static numbered circle.

Fixing these correctly (verified with real screenshots, not just code
reading) led to a design pass, and the design pass surfaced a real feature
request: let the accent color and the knob's visual style be user choices,
not fixed constants, exposed from the existing right-click context menu.

## Scope

**In scope**, all approved live in an interactive mockup during this
session (URL in session history, not reproduced here — the token values
below are the record):

- Fix `JoystickWidget`'s `WA_StyledBackground` bug.
- `BankIndicator` becomes an opaque solid accent-colored badge (same look
  in both themes — no longer theme-dependent).
- `JoystickWidget`'s base becomes a radial-gradient "socket" disc; its
  handle becomes a radial-gradient glossy accent orb.
- Knobs gain a real-time value indicator, in **two selectable styles**:
  - **A** ("number + tick"): today's numbered disc is kept; a small dot
    orbits just outside the disc's rim, positioned by the current value.
  - **B** ("needle"): the number is removed; a full needle line grows
    from the disc's center toward the rim, pointing at the current value.
  - Both point using the same sweep: value `0.0` -> 7 o'clock (210°),
    value `1.0` -> 5 o'clock (150°), sweeping clockwise the long way
    through 12 o'clock (300° total travel) — not the short way through 6.
  - This requires wiring knob CC values from `ActionEngine`'s existing
    `on_continuous` callback (added in sub-project C) through to
    `ExpandedView`, the same pattern already used for the joystick, just
    for 8 more controls (`knob_1`..`knob_8`).
- Pad press state gains a glowing accent-colored border (not just a flat
  border-color swap) — applies everywhere `PadButton`'s shared pressed QSS
  applies (`MiniView`'s pads, `ExpandedView`'s pads/buttons).
- **Accent color becomes a persisted, user-selectable setting** with 7
  choices (name -> hex, first is today's existing default, unchanged):
  `blue #3a6df0`, `violet #7c5cff`, `teal #14b8a6`, `coral #ff6b6b`,
  `amber #f59e0b`, `beige #c4a674`, `gray #8a8f9c`.
- **Knob style becomes a persisted, user-selectable setting** (`"A"` or
  `"B"`, default `"A"`).
- Both new settings are exposed from a new **"Design"** submenu in the
  existing right-click context menu (alongside `Toggle Mini/Expanded`,
  `Light Mode`/`Dark Mode`, `Always on Top`, `Quit`), each option
  checkable, current selection checked.

**Out of scope** (explicitly excluded by the user):

- The keybed's black-key border stays wired to the literal
  `config.ACCENT_HEX` module constant, unaffected by the new selectable
  accent setting. It is the one place in the app the accent choice does
  *not* reach.
- No new accent swatches beyond the 7 listed — not user-extensible/custom
  color picker.
- No change to `ActionEngine`, `midi/translator.py`, or any of
  sub-project C's scroll-handling logic — this is a pure visual/settings
  addition layered on top of already-shipped code.

## Accent color: from module constant to runtime setting

Today, `config.ACCENT_HEX`/`config.ACCENT_RGB` are import-time module
constants, baked directly into QSS f-strings wherever a file imports them
(`mini_view.py`, `expanded_view.py`, `action_config_dialog.py`). That stops
working once the accent is a runtime user choice.

- `config.ACCENT_HEX`/`config.ACCENT_RGB` **stay exactly as they are** —
  they remain the compiled-in default color and the keybed's permanent,
  unaffected source (see Out of scope above).
- New `config.py` functions, same `QSettings` pattern as
  `load_last_mode`/`save_last_mode`: `load_last_accent(default: str =
  ACCENT_HEX, *, ini_path=None) -> str` / `save_last_accent(hex_str: str,
  *, ini_path=None) -> None`, and `load_last_knob_style(default: str =
  "A", *, ini_path=None) -> str` / `save_last_knob_style(style: str, *,
  ini_path=None) -> None`.
- New `ui/accent.py` (pure, no Qt): `ACCENT_CHOICES: list[tuple[str, str]]`
  (name, hex — the 7 pairs above, in that order) and `mix(hex_color: str,
  target_rgb: tuple[int, int, int], amount: float) -> str` (returns a
  `"#rrggbb"` string — linear-interpolates each channel toward
  `target_rgb`, matching the mockup's `mix()` exactly: e.g. `mix(hex,
  (255,255,255), 0.45)` for a lighter "hi" tint, `mix(hex, (0,0,0), 0.55)`
  for a darker "lo" shade). Used to derive the joystick handle's gradient
  stops and the pad-glow color from whichever accent is currently active,
  without hand-authoring a hi/lo pair per swatch.
- `MiniView`, `ExpandedView`, `BankIndicator`, `ActionConfigDialog` each
  gain a `set_accent(hex_color: str) -> None` method (same shape as the
  existing `set_dark(dark: bool)`) that stores the value and re-triggers
  that view's own restyle path (`_layout_controls`/`_apply_style`/QSS
  rebuild) — mirroring how theme changes already propagate. Every place
  those files currently reference the imported `ACCENT_HEX`/`ACCENT_RGB`
  constants for a *styling* purpose (not the keybed) switches to reading
  `self._accent_hex`/an RGB tuple derived from it instead.
- `MainWindow` loads the saved accent/knob-style at startup, calls
  `set_accent(...)` on every view once, and re-calls it (plus re-saves)
  when the user picks a new one from the Design submenu.

## `BankIndicator`

Replace the translucent glass-pill styling entirely:

```python
_BORDER = "rgba(0,0,0,50)"

def _apply_style(self) -> None:
    self.setStyleSheet(
        f"QLabel {{ color: #ffffff; font-size: 11px; font-weight: 600; "
        f"background: {self._accent_hex}; border: 1px solid {_BORDER}; "
        f"border-radius: 8px; padding: 2px 8px; }}"
    )
```

No more `_dark`/`set_dark` branching for color — the badge looks identical
in both themes now (that's the fix: an opaque badge doesn't need a
theme-specific translucency tune, and staying identical avoids
reintroducing a dark-mode-only regression). `set_dark` can be dropped from
this class entirely (`MainWindow` stops calling
`self._bank_indicator.set_dark(...)`); `set_accent` replaces it as the
method that changes this widget's appearance.

## `JoystickWidget`

- Bug fix: add `self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,
  True)` to both `JoystickWidget.__init__` (the outer widget) and right
  after `self._handle = QFrame(self)` (the inner handle).
- Base disc QSS (in `apply_style`, replacing the flat single-color fill):
  `background: qradialgradient(cx:0.35, cy:0.3, radius:0.75, fx:0.35,
  fy:0.3, stop:0 {colors['fill_hover']}, stop:1 {colors['fill']});` (reuses
  the existing theme palette's own two fill tones — no new colors needed
  for the base, just turns the flat fill into a two-stop radial gradient
  using tones already defined in `_LIGHT`/`_DARK`).
- Handle QSS: `background: qradialgradient(cx:0.32, cy:0.28, radius:0.85,
  fx:0.32, fy:0.28, stop:0 {hi}, stop:0.55 {accent}, stop:1 {lo});
  border: 1px solid rgba(0,0,0,80);` where `hi = mix(accent, (255,255,255),
  0.45)` and `lo = mix(accent, (0,0,0), 0.55)`.

## Knobs

Knobs stop being plain `QLabel`s. New `KnobWidget(QFrame)` in
`expanded_view.py`:

- `set_value(value: float) -> None` — clamps to `0.0..1.0`, stores it,
  triggers a repaint.
- `set_style(style: str) -> None` — `"A"` or `"B"`, triggers a repaint.
- `apply_style(colors, accent_hex, diameter) -> None` — same call shape as
  `JoystickWidget.apply_style`, stores the values needed to paint.
- `paintEvent` draws, in order: the disc (same gradient treatment as the
  joystick base, radius-appropriate), then style-specific content:
  - Style A: the control's number, centered (same font/weight as today),
    then a small filled circle ("tick", ~15% of the disc's diameter)
    painted at `disc_radius + 3px` from center, at the angle
    `210 + value * 300` degrees (0° = up, clockwise-positive, matching Qt's
    `QPainter` rotation convention) — implemented via
    `painter.translate(center); painter.rotate(angle); painter.drawEllipse(...)`.
  - Style B: no number; a rounded-cap line from 15% to 85% of the disc's
    radius, same angle formula, drawn with `painter.rotate(angle)` the
    same way.
- Angle math extracted as a pure, pytest-covered function in a new
  `ui/knob_geometry.py`: `needle_angle(value: float) -> float` — returns
  `210.0 + max(0.0, min(1.0, value)) * 300.0`, matching the mockup's
  `angleFor()` exactly (this is the only piece of this sub-project's UI
  work that's pure/pytest-friendly, per the same extraction pattern this
  project already uses for `keybed.py`/`scaling.py`/`joystick_geometry.py`).

`ExpandedView` swaps `self._knobs: dict[str, QLabel]` for `self._knobs:
dict[str, KnobWidget]`, gains `set_knob_style(style: str) -> None`
(propagates to every `KnobWidget`) and `set_knob_value(control: str, value:
float) -> None` (looks up the right widget, calls `set_value`).

## Wiring knob values (`MainWindow`)

Sub-project C's `_apply_joystick_continuous` already demonstrates the
pattern for one pair of controls; this extends the same `on_continuous`
callback to the 8 knob controls too, without a repeat timer (knobs don't
need hold-to-repeat — a knob's value only changes when the physical knob
actually turns, unlike the spring-loaded joystick):

```python
def _apply_joystick_continuous(self, control: str, value: float) -> None:
    if control in self._joystick_values:
        ...  # unchanged from sub-project C
    elif control.startswith("knob_"):
        self._expanded_view.set_knob_value(control, value)
```

(Renaming this method is out of scope for this spec — it already handles
"a continuous value arrived, mirror it visually," knobs are just another
branch of that same responsibility.)

## Pad press glow

In `mini_view.py`'s and `expanded_view.py`'s shared pressed-state QSS,
replace the flat `border: 1px solid {accent}` with a glow:

```python
f"QPushButton:pressed {{ ...; border: 1px solid {accent_hex}; "
f"outline: none; }}"
```

Qt's stylesheet `box-shadow` support is unreliable across widget types, so
the glow itself needs a real `QGraphicsDropShadowEffect` (or an
equivalent glow effect) applied to a `PadButton` on press and removed on
release, colored from `self._accent_hex`, rather than a CSS box-shadow —
this is a Qt-specific implementation detail the plan should size
appropriately (event handlers already exist in `PadButton` to hook into:
`mousePressEvent`already starts the click-debounce timer; the glow effect
attaches/detaches at the same points, or `mousePressEvent`/`mouseReleaseEvent`
if a cleaner hook is needed).

## "Design" context menu

`MainWindow._build_tray()` gains one more `menu.addSeparator()` + submenu,
placed after `Always on Top` and before `Quit`. `QActionGroup` in this
PySide6 version lives in `PySide6.QtGui`, not `QtWidgets` (verified
directly against the installed package — `from PySide6.QtWidgets import
QActionGroup` raises `ImportError` here):

```python
design_menu = menu.addMenu("Design")
knob_style_group = QActionGroup(design_menu)
for style, label in [("A", "Knob: Number + Tick"), ("B", "Knob: Needle")]:
    action = design_menu.addAction(label)
    action.setCheckable(True)
    action.setActionGroup(knob_style_group)
    action.setChecked(style == self._knob_style)
    action.triggered.connect(lambda checked, s=style: self._set_knob_style(s))
design_menu.addSeparator()
accent_group = QActionGroup(design_menu)
for name, hex_color in ACCENT_CHOICES:
    action = design_menu.addAction(_accent_icon(hex_color), name.capitalize())
    action.setCheckable(True)
    action.setActionGroup(accent_group)
    action.setChecked(hex_color == self._accent_hex)
    action.triggered.connect(lambda checked, h=hex_color: self._set_accent(h))
```

`_accent_icon(hex_color: str) -> QIcon` draws a small solid-color circle
(same `QPainter`-on-`QPixmap` pattern `_tray_icon()` already uses in this
file) so each accent choice shows its actual color next to its name, not
just text.

`_set_accent`/`_set_knob_style` update `self._accent_hex`/`self._knob_style`,
save via `save_last_accent`/`save_last_knob_style`, and call `set_accent`/
`set_knob_style` on every relevant view (mirroring `_set_theme`'s existing
shape).

## Testing

- `ui/accent.py`: `mix()` pytest-covered (pure function — check both
  directions, 0.0/1.0 boundaries, a mid-value).
- `ui/knob_geometry.py`: `needle_angle()` pytest-covered (0.0 -> 210,
  1.0 -> 510 mod 360 = 150, 0.5 -> 360 mod 360 = 0, clamping outside
  0..1).
- `config.py`'s new load/save functions: pytest-covered, same style as
  the existing `load_last_mode`/`save_last_mode` tests (round-trip via a
  temp `ini_path`).
- Everything else touched (`BankIndicator`, `JoystickWidget`, `KnobWidget`,
  `MiniView`'s pad glow, `MainWindow`'s Design menu) is Qt widget code —
  not pytest-covered per this repo's documented policy; verified via an
  off-screen smoke script (render each accent, each knob style, assert
  paint doesn't raise, assert a real screenshot shows a legible badge in
  both themes and a circular — not square — joystick handle) plus a live
  `python -m mpk_deck` check.

## Resuming sub-project C

Once this lands, sub-project C's Task 8 review (paused mid-dispatch when
this design work was requested) and Task 9 (docs) resume exactly where
they left off — nothing in this spec changes any of C's already-merged
commits' behavior, only adds a styling/settings layer on top.
