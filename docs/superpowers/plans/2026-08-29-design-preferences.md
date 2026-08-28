# Design Preferences (Accent Color + Knob Style) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `BankIndicator` dark-mode readability bug and the `JoystickWidget` square-handle rendering bug, add a real-time knob value indicator (two selectable styles), and make the app's accent color and knob style persisted, user-selectable settings exposed from the right-click context menu.

**Architecture:** A new pure `ui/accent.py` (7 named accent swatches + a hex color-mix helper + a hex-to-rgb-string helper) and `ui/knob_geometry.py` (the 7-to-5-o'clock angle formula) replace ad-hoc per-file color math. `config.py` gains two more `QSettings`-backed load/save pairs, matching the existing `load_last_mode`/`save_last_theme` pattern exactly. Every view that currently bakes `config.ACCENT_HEX`/`ACCENT_RGB` into module-level QSS at import time (`MiniView`, `ExpandedView`, `BankIndicator`, `ActionConfigDialog`) switches to reading a runtime accent value instead, propagated the same way theme changes already propagate (`set_dark(dark)` -> new `set_accent(hex_color)`). Knobs stop being plain `QLabel`s and become a new `KnobWidget(QFrame)` with a `paintEvent`-drawn value indicator in one of two styles. `MainWindow` loads/saves the two new settings, builds a new "Design" submenu in the existing tray context menu, and extends the `on_continuous`-callback wiring sub-project C already built for the joystick to cover the 8 knob controls too.

**Tech Stack:** No new dependencies — same PySide6/`QSettings` stack as the rest of the app.

**Spec:** `docs/superpowers/specs/2026-08-29-design-preferences.md`

## Global Constraints

- The keybed's black-key border stays wired to the literal `config.ACCENT_RGB` module constant — it is the one place in the app the new selectable accent does **not** reach (explicit user decision).
- `config.ACCENT_HEX`/`config.ACCENT_RGB` themselves are unchanged and stay the compiled-in default; the new settings only add a *runtime override* layered on top via `QSettings`, never replacing the constants.
- Accent choices (name, hex), in this exact order — index 0 is today's existing default, unchanged: `blue #3a6df0`, `violet #7c5cff`, `teal #14b8a6`, `coral #ff6b6b`, `amber #f59e0b`, `beige #c4a674`, `gray #8a8f9c`.
- Knob sweep: value `0.0` -> `210°` (7 o'clock), value `1.0` -> `510°`/`150°` (5 o'clock), clockwise through 12 o'clock (300° total travel) — `0°` = up, increasing clockwise, matching `QPainter.rotate()`'s convention.
- Two knob styles, both real, both user-selectable (not a dev preview — the spec's mockup comparison was exploratory, the plan ships both): `"A"` keeps the control number and orbits a small dot outside the disc's rim; `"B"` drops the number and draws a full needle from the disc's center, no dot.
- Mouse-drag-to-preview and hardware-driven visual updates for the joystick (sub-project C) are unaffected by this plan — only the joystick's *visual styling* changes here, not its interaction logic.
- `ui/accent.py`, `ui/knob_geometry.py`, `config.py`'s new functions: pytest-covered (TDD). `BankIndicator`, `JoystickWidget`, `KnobWidget`, `MiniView`'s pad glow, `ActionConfigDialog`'s accent param, `MainWindow`'s Design menu: not pytest-covered per this repo's documented policy (`mpk-deck/CLAUDE.md`) — verify manually via `python -m mpk_deck` or an off-screen smoke script.
- No git worktree — commit and push directly to `main` after each task (solo project, standing authorization per `mpk-deck/CLAUDE.md`, established 2026-08-19).

---

### Task 1: `ui/accent.py` — accent swatches + color math

**Files:**
- Create: `src/mpk_deck/ui/accent.py`
- Test: `tests/ui/test_accent.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ACCENT_CHOICES: list[tuple[str, str]]` (7 `(name, hex)` pairs, order per Global Constraints), `mix(hex_color: str, target_rgb: tuple[int, int, int], amount: float) -> str` (returns `"#rrggbb"`), `hex_to_rgb_str(hex_color: str) -> str` (returns `"r,g,b"`, e.g. `"58,109,240"` — matches `config.ACCENT_RGB`'s existing format). Used by Tasks 4-8.

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/test_accent.py`:

```python
from mpk_deck.ui.accent import ACCENT_CHOICES, hex_to_rgb_str, mix


def test_accent_choices_first_entry_is_current_default():
    assert ACCENT_CHOICES[0] == ("blue", "#3a6df0")


def test_accent_choices_has_seven_entries():
    assert len(ACCENT_CHOICES) == 7


def test_accent_choices_names_are_unique():
    names = [name for name, _ in ACCENT_CHOICES]
    assert len(names) == len(set(names))


def test_hex_to_rgb_str_matches_existing_accent_rgb_format():
    assert hex_to_rgb_str("#3a6df0") == "58,109,240"


def test_mix_zero_amount_returns_original():
    assert mix("#3a6df0", (255, 255, 255), 0.0) == "#3a6df0"


def test_mix_full_amount_returns_target():
    assert mix("#3a6df0", (255, 255, 255), 1.0) == "#ffffff"


def test_mix_toward_black_at_half():
    assert mix("#3a6df0", (0, 0, 0), 0.5) == "#1d3678"


def test_mix_toward_white_at_045():
    assert mix("#3a6df0", (255, 255, 255), 0.45) == "#93aff7"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_accent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mpk_deck.ui.accent'`

- [ ] **Step 3: Implement it**

Create `src/mpk_deck/ui/accent.py`:

```python
ACCENT_CHOICES: list[tuple[str, str]] = [
    ("blue", "#3a6df0"),
    ("violet", "#7c5cff"),
    ("teal", "#14b8a6"),
    ("coral", "#ff6b6b"),
    ("amber", "#f59e0b"),
    ("beige", "#c4a674"),
    ("gray", "#8a8f9c"),
]


def hex_to_rgb_str(hex_color: str) -> str:
    """"#3a6df0" -> "58,109,240" - matches config.ACCENT_RGB's existing format."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"{r},{g},{b}"


def mix(hex_color: str, target_rgb: tuple[int, int, int], amount: float) -> str:
    """Linearly interpolate hex_color toward target_rgb by amount (0.0..1.0).
    Used to derive lighter/darker gradient stops from whichever accent is active,
    without hand-authoring a light/dark pair per swatch."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    tr, tg, tb = target_rgb
    mr = round(r + (tr - r) * amount)
    mg = round(g + (tg - g) * amount)
    mb = round(b + (tb - b) * amount)
    return f"#{mr:02x}{mg:02x}{mb:02x}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_accent.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/accent.py tests/ui/test_accent.py
git commit -m "feat: add accent color swatches and hex color-mix helper"
git push
```

---

### Task 2: `ui/knob_geometry.py` — sweep angle math

**Files:**
- Create: `src/mpk_deck/ui/knob_geometry.py`
- Test: `tests/ui/test_knob_geometry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `needle_angle(value: float) -> float` — clamps `value` to `0.0..1.0`, returns degrees per Global Constraints' sweep formula. Used by Task 6.

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/test_knob_geometry.py`:

```python
from mpk_deck.ui.knob_geometry import needle_angle


def test_needle_angle_min_is_210():
    assert needle_angle(0.0) == 210.0


def test_needle_angle_max_is_510():
    assert needle_angle(1.0) == 510.0


def test_needle_angle_mid_is_360():
    assert needle_angle(0.5) == 360.0


def test_needle_angle_clamps_below_zero():
    assert needle_angle(-0.5) == 210.0


def test_needle_angle_clamps_above_one():
    assert needle_angle(1.5) == 510.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_knob_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mpk_deck.ui.knob_geometry'`

- [ ] **Step 3: Implement it**

Create `src/mpk_deck/ui/knob_geometry.py`:

```python
def needle_angle(value: float) -> float:
    """0.0 -> 210deg (7 o'clock), 1.0 -> 510deg (5 o'clock, i.e. 150deg mod 360),
    clockwise through 12 o'clock (300deg total travel). 0deg = up, increasing
    clockwise - matches QPainter.rotate()'s convention directly, no conversion
    needed at the call site. Returned unwrapped (can exceed 360) since
    QPainter.rotate() handles that correctly."""
    return 210.0 + max(0.0, min(1.0, value)) * 300.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_knob_geometry.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/knob_geometry.py tests/ui/test_knob_geometry.py
git commit -m "feat: add needle_angle knob sweep math"
git push
```

---

### Task 3: `config.py` — accent + knob style persistence

**Files:**
- Modify: `src/mpk_deck/config.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: `ACCENT_HEX` (already in this file).
- Produces: `load_last_accent(default: str = ACCENT_HEX, *, ini_path: str | None = None) -> str`, `save_last_accent(accent_hex: str, *, ini_path: str | None = None) -> None`, `load_last_knob_style(default: str = "A", *, ini_path: str | None = None) -> str`, `save_last_knob_style(style: str, *, ini_path: str | None = None) -> None`. Used by Task 8.

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_config.py` (add `load_last_accent`, `save_last_accent`, `load_last_knob_style`, `save_last_knob_style`, and `ACCENT_HEX` to the existing import block at the top of the file):

```python
from mpk_deck.config import (
    ACCENT_HEX,
    load_last_accent,
    load_last_always_on_top,
    load_last_knob_style,
    load_last_mode,
    load_last_theme,
    save_last_accent,
    save_last_always_on_top,
    save_last_knob_style,
    save_last_mode,
    save_last_theme,
)
```

Then append these tests to the end of the file:

```python
def test_save_and_load_last_accent_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_accent("#7c5cff", ini_path=ini_path)
    assert load_last_accent(ini_path=ini_path) == "#7c5cff"


def test_load_last_accent_defaults_to_accent_hex(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_accent(ini_path=ini_path) == ACCENT_HEX


def test_save_and_load_last_knob_style_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_knob_style("B", ini_path=ini_path)
    assert load_last_knob_style(ini_path=ini_path) == "B"


def test_load_last_knob_style_defaults_to_a(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_knob_style(ini_path=ini_path) == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: the 6 pre-existing tests pass; the 4 new ones FAIL with `ImportError: cannot import name 'load_last_accent'`

- [ ] **Step 3: Implement the new settings functions**

Append to the end of `src/mpk_deck/config.py`:

```python
def load_last_accent(default: str = ACCENT_HEX, *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/accent", default)


def save_last_accent(accent_hex: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/accent", accent_hex)
    settings.sync()


def load_last_knob_style(default: str = "A", *, ini_path: str | None = None) -> str:
    settings = _get_settings(ini_path)
    return settings.value("ui/knob_style", default)


def save_last_knob_style(style: str, *, ini_path: str | None = None) -> None:
    settings = _get_settings(ini_path)
    settings.setValue("ui/knob_style", style)
    settings.sync()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/config.py tests/test_config.py
git commit -m "feat: persist last-used accent color and knob style"
git push
```

---

### Task 4: `ui/bank_indicator.py` — opaque badge (fixes dark-mode readability)

**Files:**
- Modify: `src/mpk_deck/ui/bank_indicator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `BankIndicator.set_accent(accent_hex: str) -> None` (new — replaces `set_dark`, which is removed entirely from this class). `set_bank_name` is unchanged. Used by Task 8.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents of `src/mpk_deck/ui/bank_indicator.py` with:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from mpk_deck.config import ACCENT_HEX

_BORDER = "rgba(0,0,0,50)"


class BankIndicator(QLabel):
    """Shows the active bank's display name as a solid accent-colored badge.

    Opaque by design, not a translucent glass pill - the previous glass-pill
    treatment was unreadable in dark mode (its fill alpha gave no real contrast
    against the panel behind it). An opaque badge looks identical in both themes,
    so it needs no theme branching - set_accent is the only thing that changes
    its appearance now.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._accent_hex = ACCENT_HEX
        self.set_bank_name("")
        self._apply_style()

    def set_bank_name(self, name: str) -> None:
        self.setText(name)
        self.adjustSize()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: #ffffff; font-size: 11px; font-weight: 600; "
            f"background: {self._accent_hex}; border: 1px solid {_BORDER}; "
            f"border-radius: 8px; padding: 2px 8px; }}"
        )
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from mpk_deck.ui.bank_indicator import BankIndicator; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 3: Commit**

```bash
git add src/mpk_deck/ui/bank_indicator.py
git commit -m "fix: replace BankIndicator's unreadable glass pill with an opaque accent badge"
git push
```

---

### Task 5: `ui/mini_view.py` — accent flow-through + pad press glow

**Files:**
- Modify: `src/mpk_deck/ui/mini_view.py`

**Interfaces:**
- Consumes: `hex_to_rgb_str` (Task 1).
- Produces: `PadButton.set_accent(accent_hex: str) -> None` (new — updates the button's press-glow color; `PadButton` is shared with `ExpandedView`, Task 6 reuses this same method). `MiniView.set_accent(accent_hex: str) -> None` (new). `set_dark` keeps its existing signature/behavior (theme only, no accent coupling). Used by Task 6 (imports `PadButton`) and Task 8.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents of `src/mpk_deck/ui/mini_view.py` with:

```python
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX
from mpk_deck.core.action_registry import Binding
from mpk_deck.ui.accent import hex_to_rgb_str
from mpk_deck.ui.action_config_dialog import ACTION_GLYPHS, ACTION_LABELS
from mpk_deck.ui.grid_layout import compute_pad_rects
from mpk_deck.ui.window_grip import WindowGripMixin

PAD_ORDER = ["pad_5", "pad_6", "pad_7", "pad_8", "pad_1", "pad_2", "pad_3", "pad_4"]

COLS, ROWS = 4, 2
ASPECT = COLS / ROWS
MARGIN, SPACING = 20, 8
BORDER_VISUAL = 2  # thin visible edge-light inside the wider (BORDER) grab zone


def _light_qss(accent_hex: str, accent_rgb: str) -> str:
    return f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255,255,255,120), stop:1 rgba(235,240,255,150));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({accent_rgb},130);
}}
QPushButton {{
    background: rgba(255,255,255,140);
    border: 1px solid rgba(120,120,140,90);
    border-radius: 12px;
    color: #23242b;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,190); }}
QPushButton:pressed {{ background: rgba(220,225,240,190); border: 1px solid {accent_hex}; }}
"""


def _dark_qss(accent_hex: str, accent_rgb: str) -> str:
    return f"""
QWidget#miniPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20,22,28,217), stop:1 rgba(10,12,16,191));
    border-radius: 16px;
    border: {BORDER_VISUAL}px solid rgba({accent_rgb},100);
}}
QPushButton {{
    background: rgba(255,255,255,18);
    border: 1px solid rgba(255,255,255,38);
    border-radius: 12px;
    color: #f2f4f8;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,34); }}
QPushButton:pressed {{ background: rgba(255,255,255,10); border: 1px solid {accent_hex}; }}
"""


class PadButton(QPushButton):
    """A button that tells single clicks (trigger) apart from double clicks (configure).

    Also owns the accent-colored press glow (a QGraphicsDropShadowEffect kept
    attached permanently and toggled via setEnabled, rather than
    attached/detached per press - simpler and avoids effect-teardown timing
    issues). Shared by MiniView and ExpandedView, so the glow behavior is
    identical everywhere a pad/button reacts to a press.
    """

    activated = Signal()
    configure_requested = Signal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)
        self.clicked.connect(self._on_clicked)
        self._accent_hex = ACCENT_HEX
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(16)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(self._accent_hex))
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        self._glow.setColor(QColor(accent_hex))

    def _on_clicked(self) -> None:
        self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._click_timer.stop()
        self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._glow.setEnabled(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._glow.setEnabled(False)
        super().mouseReleaseEvent(event)


class MiniView(WindowGripMixin, QWidget):
    pad_activated = Signal(str)
    pad_configure_requested = Signal(str)

    def __init__(self, labels: dict[str, str] | None = None, dark: bool = False, parent=None) -> None:
        super().__init__(parent, aspect=ASPECT, min_width=240)
        self.setObjectName("miniPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._labels = labels or {}
        self._dark = dark
        self._accent_hex = ACCENT_HEX
        self._pads: dict[str, PadButton] = {}
        for control in PAD_ORDER:
            button = PadButton(self._labels.get(control, control.upper()), self)
            button.activated.connect(lambda c=control: self.pad_activated.emit(c))
            button.configure_requested.connect(lambda c=control: self.pad_configure_requested.emit(c))
            self._pads[control] = button
        self._apply_style()
        self._layout_pads()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_style()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        for pad in self._pads.values():
            pad.set_accent(accent_hex)
        self._apply_style()

    def _apply_style(self) -> None:
        accent_rgb = hex_to_rgb_str(self._accent_hex)
        qss = _dark_qss(self._accent_hex, accent_rgb) if self._dark else _light_qss(self._accent_hex, accent_rgb)
        self.setStyleSheet(qss)

    def update_bindings(self, bindings: dict[str, Binding]) -> None:
        """Reflect each pad's bound action as a big icon instead of the bare control id."""
        for control, button in self._pads.items():
            binding = bindings.get(control)
            if binding is None:
                button.setText(self._labels.get(control, control.upper()))
                button.setToolTip("")
            else:
                glyph = ACTION_GLYPHS.get(binding.action, "")
                custom_label = self._labels.get(control)
                button.setText(f"{glyph}\n{custom_label}" if custom_label else glyph or control.upper())
                button.setToolTip(ACTION_LABELS.get(binding.action, binding.action))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_pads()

    def _layout_pads(self) -> None:
        rects = compute_pad_rects(
            self.width(), self.height(), cols=COLS, rows=ROWS, margin=MARGIN, spacing=SPACING
        )
        for control, rect in zip(PAD_ORDER, rects):
            self._pads[control].setGeometry(rect)
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: all pre-existing tests pass (this task adds no new pytest tests - `mini_view.py` has no pytest coverage by project convention; this confirms the rewrite didn't break anything importing `PadButton`, e.g. `expanded_view.py`).

- [ ] **Step 3: Commit**

```bash
git add src/mpk_deck/ui/mini_view.py
git commit -m "feat: add accent-color flow-through and press glow to MiniView pads"
git push
```

---

### Task 6: `ui/expanded_view.py` — JoystickWidget fix/redesign + KnobWidget

**Files:**
- Modify: `src/mpk_deck/ui/expanded_view.py`

**Interfaces:**
- Consumes: `mix`, `hex_to_rgb_str` (Task 1), `needle_angle` (Task 2), `PadButton` (Task 5, already imported by this file - its new `set_accent` method is now available for free).
- Produces: `ExpandedView.set_accent(accent_hex: str) -> None` (new), `ExpandedView.set_knob_style(style: str) -> None` (new), `ExpandedView.set_knob_value(control: str, value: float) -> None` (new - `control` is `"knob_1"`..`"knob_8"`). `set_dark`, `set_joystick_deflection` keep their existing signatures. New `KnobWidget(QFrame)` class (not exported/used outside this file). Used by Task 8.

- [ ] **Step 1: Replace the whole file**

Replace the entire contents of `src/mpk_deck/ui/expanded_view.py` with:

```python
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton, QWidget

from mpk_deck.config import ACCENT_HEX, ACCENT_RGB
from mpk_deck.ui.accent import hex_to_rgb_str, mix
from mpk_deck.ui.joystick_geometry import clamp_deflection
from mpk_deck.ui.keybed import NUM_KEYS, compute_keybed_rects, is_black_key
from mpk_deck.ui.knob_geometry import needle_angle
from mpk_deck.ui.mini_view import PadButton
from mpk_deck.ui.scaling import compute_scale
from mpk_deck.ui.window_grip import WindowGripMixin

PAD_LABELS_TOP = ["pad_5", "pad_6", "pad_7", "pad_8"]
PAD_LABELS_BOTTOM = ["pad_1", "pad_2", "pad_3", "pad_4"]
KNOB_LABELS_TOP = ["knob_1", "knob_2", "knob_3", "knob_4"]
KNOB_LABELS_BOTTOM = ["knob_5", "knob_6", "knob_7", "knob_8"]

ASPECT = 312 / 184
BORDER_VISUAL = 2  # thin visible edge-light inside the wider (window_grip.BORDER) grab zone
BASE_WIDTH = 480  # reference width the spec's fixed-px control sizes were measured at

LEFT_BUTTONS = [
    ("arp_on_off", "ON", "Arp On/Off"),
    ("tap_tempo", "TAP", "Tap Tempo"),
    ("octave_down", "OCT▼", "Octave Down"),
    ("octave_up", "OCT▲", "Octave Up"),
    ("full_level", "FULL", "Full Level"),
    ("note_repeat", "RPT", "Note Repeat"),
]
RIGHT_BUTTONS = [
    ("bank_ab", "BANK", "Bank A/B"),
    ("cc", "CC", "CC"),
    ("prog_change", "CHG", "Prog Change"),
    ("prog_select", "SEL", "Prog Select"),
]
GROUPED_RIGHT_BUTTONS = ["bank_ab", "cc", "prog_change"]  # spec: bordered as one group, SEL set apart

BASE_JOYSTICK_D = 40
BASE_BTN_W, BASE_BTN_H = 34, 16
BASE_BTN_FONT = 7
BASE_PAD_FONT = 9
BASE_KNOB_D = 24
BASE_KNOB_FONT = 8

# Matches MiniView's palette so both views read as one design system.
_LIGHT = {
    "fill": "rgba(255,255,255,140)",
    "fill_hover": "rgba(255,255,255,190)",
    "fill_pressed": "rgba(220,225,240,190)",
    "border": "rgba(120,120,140,90)",
    "text": "#23242b",
}
_DARK = {
    "fill": "rgba(255,255,255,18)",
    "fill_hover": "rgba(255,255,255,34)",
    "fill_pressed": "rgba(255,255,255,10)",
    "border": "rgba(255,255,255,38)",
    "text": "#f2f4f8",
}
# Keybed colors are theme-tinted but always readable as "black key vs white key",
# independent of app theme (a piano keybed reads by its own convention, not the app's).
# Deliberately NOT accent-selectable - wired to the literal config.ACCENT_RGB constant,
# unaffected by the user's chosen accent (see docs/superpowers/specs/2026-08-29-
# design-preferences.md's Out of scope section).
_KEY_COLORS = {
    True: {  # dark theme
        "white": ("#e8e6df", "#33322c"),
        "black": ("#14161c", f"rgba({ACCENT_RGB},140)"),
    },
    False: {  # light theme
        "white": ("#fbfbfa", "#c9c6bd"),
        "black": ("#2b2620", f"rgba({ACCENT_RGB},140)"),
    },
}


class _DebouncedKey(QFrame):
    """A keybed key: single click activates (debounced), double click configures.

    QFrame has no QAbstractButton `clicked` signal to build on, so this mirrors
    PadButton's (mini_view.py) timer-based debounce directly on the raw mouse events.
    """

    activated = Signal()
    configure_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.activated.emit)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start(QApplication.doubleClickInterval())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._click_timer.stop()
        self.configure_requested.emit()
        super().mouseDoubleClickEvent(event)


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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._handle = QFrame(self)
        self._handle.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._x = 0.0
        self._y = 0.0

    def set_deflection(self, x: float, y: float) -> None:
        self._x = max(-1.0, min(1.0, x))
        self._y = max(-1.0, min(1.0, y))
        self._reposition_handle()

    def apply_style(self, colors: dict[str, str], accent_hex: str, diameter: int) -> None:
        self.setFixedSize(diameter, diameter)
        self.setStyleSheet(
            f"QFrame {{ background: qradialgradient(cx:0.35, cy:0.3, radius:0.75, fx:0.35, fy:0.3, "
            f"stop:0 {colors['fill_hover']}, stop:1 {colors['fill']}); "
            f"border: 2px solid {accent_hex}; border-radius: {diameter // 2}px; }}"
        )
        hi = mix(accent_hex, (255, 255, 255), 0.45)
        lo = mix(accent_hex, (0, 0, 0), 0.55)
        self._handle.setStyleSheet(
            f"QFrame {{ background: qradialgradient(cx:0.32, cy:0.28, radius:0.85, fx:0.32, fy:0.28, "
            f"stop:0 {hi}, stop:0.55 {accent_hex}, stop:1 {lo}); "
            f"border: 1px solid rgba(0,0,0,80); border-radius: 999px; }}"
        )
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


class KnobWidget(QFrame):
    """Shows a knob's real-time value as a rotating indicator, in one of two
    selectable styles (see set_style):

    - "A": keeps the control's number centered, and orbits a small dot just
      outside the disc's rim, positioned by the current value.
    - "B": drops the number, draws a full needle from the disc's center toward
      the rim, positioned by the current value.

    Both use the same sweep (ui/knob_geometry.py's needle_angle): value 0.0 ->
    7 o'clock, value 1.0 -> 5 o'clock, clockwise through 12."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label = label
        self._value = 0.0
        self._style = "A"
        self._colors = _DARK
        self._accent_hex = ACCENT_HEX

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))
        self.update()

    def apply_style(
        self, colors: dict[str, str], accent_hex: str, diameter: int, font_px: float, style: str
    ) -> None:
        self._colors = colors
        self._accent_hex = accent_hex
        self._style = style
        self.setFixedSize(diameter, diameter)
        font = self.font()
        font.setPixelSize(max(1, round(font_px)))
        font.setWeight(700)  # matches the old QLabel knob styling's font-weight: 700
        self.setFont(font)
        accent_rgb = hex_to_rgb_str(accent_hex)
        self.setStyleSheet(
            f"QFrame {{ background: qradialgradient(cx:0.35, cy:0.3, radius:0.75, fx:0.35, fy:0.3, "
            f"stop:0 {colors['fill_hover']}, stop:1 {colors['fill']}); "
            f"border: 2px solid rgba({accent_rgb},170); border-radius: {diameter // 2}px; }}"
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        r = d / 2
        accent = QColor(self._accent_hex)

        if self._style == "A":
            painter.setPen(QColor(self._colors["text"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label)
            painter.save()
            painter.translate(QPointF(r, r))
            painter.rotate(needle_angle(self._value))
            painter.setBrush(accent)
            painter.setPen(Qt.PenStyle.NoPen)
            tick_r = max(1.0, d * 0.06)
            painter.drawEllipse(QPointF(0, -(r + 3)), tick_r, tick_r)
            painter.restore()
        else:
            painter.save()
            painter.translate(QPointF(r, r))
            painter.rotate(needle_angle(self._value))
            pen = QPen(accent)
            pen.setWidthF(max(2.0, d * 0.05))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(0, -0.15 * r), QPointF(0, -0.85 * r))
            painter.restore()
        painter.end()


def _button_qss(colors: dict[str, str], font_px: float, radius: float, accent_hex: str) -> str:
    return (
        f"QPushButton {{ background: {colors['fill']}; border: 1px solid {colors['border']}; "
        f"border-radius: {radius:.0f}px; color: {colors['text']}; font-size: {font_px:.0f}px; "
        f"font-weight: 600; padding: 0px; margin: 0px; }}"
        f"QPushButton:hover {{ background: {colors['fill_hover']}; }}"
        f"QPushButton:pressed {{ background: {colors['fill_pressed']}; border: 1px solid {accent_hex}; }}"
    )


class ExpandedView(WindowGripMixin, QWidget):
    control_activated = Signal(str)
    control_configure_requested = Signal(str)

    def __init__(self, dark: bool = False, parent=None) -> None:
        super().__init__(parent, aspect=ASPECT, min_width=BASE_WIDTH)
        self.setObjectName("expandedPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(BASE_WIDTH, 284)  # keeps the 312:184 aspect ratio roughly intact
        self._dark = dark
        self._accent_hex = ACCENT_HEX
        self._knob_style = "A"

        self._joystick = JoystickWidget(self)
        self._joystick.axis_configure_requested.connect(self.control_configure_requested.emit)

        self._buttons: dict[str, PadButton] = {}
        for control, text, tooltip in LEFT_BUTTONS + RIGHT_BUTTONS:
            btn = PadButton(text, self)
            btn.setToolTip(tooltip)
            btn.activated.connect(lambda c=control: self.control_activated.emit(c))
            btn.configure_requested.connect(lambda c=control: self.control_configure_requested.emit(c))
            self._buttons[control] = btn

        self._bank_group = QFrame(self)
        self._bank_group.lower()

        self._pads: dict[str, PadButton] = {}
        for control in PAD_LABELS_TOP + PAD_LABELS_BOTTOM:
            btn = PadButton(control.upper(), self)
            btn.activated.connect(lambda c=control: self.control_activated.emit(c))
            btn.configure_requested.connect(lambda c=control: self.control_configure_requested.emit(c))
            self._pads[control] = btn

        self._knobs: dict[str, KnobWidget] = {}
        for control in KNOB_LABELS_TOP + KNOB_LABELS_BOTTOM:
            self._knobs[control] = KnobWidget(control.split("_")[1].upper(), self)

        # 25 keys (15 white + 10 black), C to C over 2 octaves + 1 — matches the physical keybed.
        self._keys: dict[int, _DebouncedKey] = {}
        for i in range(NUM_KEYS):
            key = _DebouncedKey(self)
            key.activated.connect(lambda k=i: self.control_activated.emit(f"key_{k}"))
            key.configure_requested.connect(lambda k=i: self.control_configure_requested.emit(f"key_{k}"))
            self._keys[i] = key

        self.set_dark(dark)  # also lays out controls

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        bg = (
            "rgba(20,22,28,217)"
            if dark
            else "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,120), "
            "stop:1 rgba(235,240,255,150))"  # matches MiniView's white glass, not accent-tinted
        )
        border_alpha = 100 if dark else 130
        accent_rgb = hex_to_rgb_str(self._accent_hex)
        self.setStyleSheet(
            f"QWidget#expandedPanel {{ background: {bg}; border-radius: 16px; "
            f"border: {BORDER_VISUAL}px solid rgba({accent_rgb},{border_alpha}); }}"
        )
        self._bank_group.setStyleSheet(
            f"QFrame {{ border: 1px solid rgba({accent_rgb},170); border-radius: 4px; "
            f"background: rgba({accent_rgb},18); }}"
        )
        self._layout_controls()

    def set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        for btn in list(self._buttons.values()) + list(self._pads.values()):
            btn.set_accent(accent_hex)
        self.set_dark(self._dark)  # re-derives panel/bank-group border color, and re-layouts

    def set_knob_style(self, style: str) -> None:
        self._knob_style = style
        self._layout_controls()

    def set_joystick_deflection(self, x: float, y: float) -> None:
        self._joystick.set_deflection(x, y)

    def set_knob_value(self, control: str, value: float) -> None:
        knob = self._knobs.get(control)
        if knob is not None:
            knob.set_value(value)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._layout_controls()

    def _layout_controls(self) -> None:
        w, h = self.width(), self.height()
        scale = compute_scale(w, base_width=BASE_WIDTH)
        colors = _DARK if self._dark else _LIGHT

        btn_w, btn_h = round(BASE_BTN_W * scale), round(BASE_BTN_H * scale)
        btn_font = BASE_BTN_FONT * scale
        joy_d = round(BASE_JOYSTICK_D * scale)
        pad_font = BASE_PAD_FONT * scale
        knob_d = round(BASE_KNOB_D * scale)
        knob_font = BASE_KNOB_FONT * scale

        self._joystick.apply_style(colors, self._accent_hex, joy_d)

        btn_qss = _button_qss(colors, btn_font, radius=4 * scale, accent_hex=self._accent_hex)
        for control, btn in self._buttons.items():
            btn.setStyleSheet(btn_qss)
            btn.setFixedSize(btn_w, btn_h)

        pad_qss = _button_qss(colors, pad_font, radius=12 * scale, accent_hex=self._accent_hex)
        for btn in self._pads.values():
            btn.setStyleSheet(pad_qss)

        for knob in self._knobs.values():
            knob.apply_style(colors, self._accent_hex, knob_d, knob_font, self._knob_style)

        left_x = int(0.03 * w)
        left_y = int(0.04 * h)
        self._joystick.move(left_x, left_y)
        row_y = left_y + joy_d + 5
        for i in range(0, len(LEFT_BUTTONS), 2):
            a_control = LEFT_BUTTONS[i][0]
            b_control = LEFT_BUTTONS[i + 1][0]
            self._buttons[a_control].move(left_x, row_y)
            self._buttons[b_control].move(left_x + btn_w + 4, row_y)
            row_y += btn_h + 5

        pad_x, pad_y = int(0.18 * w), int(0.02 * h)
        pad_w, pad_h = int(0.42 * w) // 4, int(0.36 * h) // 2
        for i, control in enumerate(PAD_LABELS_TOP):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y, pad_w - 4, pad_h - 4)
        for i, control in enumerate(PAD_LABELS_BOTTOM):
            self._pads[control].setGeometry(pad_x + i * pad_w, pad_y + pad_h, pad_w - 4, pad_h - 4)

        knob_x, knob_y = int(0.63 * w), int(0.04 * h)
        knob_cell_w = int(0.34 * w) // 4
        for i, control in enumerate(KNOB_LABELS_TOP):
            cx = knob_x + i * knob_cell_w + (knob_cell_w - knob_d) // 2
            self._knobs[control].move(cx, knob_y)
        knob_row_gap = round(14 * scale)
        for i, control in enumerate(KNOB_LABELS_BOTTOM):
            cx = knob_x + i * knob_cell_w + (knob_cell_w - knob_d) // 2
            self._knobs[control].move(cx, knob_y + knob_d + knob_row_gap)

        btn_row_x = knob_x + int(0.02 * w)
        btn_row_y = int(0.32 * h)
        bx = btn_row_x
        for control in GROUPED_RIGHT_BUTTONS:
            self._buttons[control].move(bx, btn_row_y)
            bx += btn_w + 4
        group_pad = 3
        content_right = bx - 4  # bx overshoots by the trailing gap after the last grouped button
        self._bank_group.setGeometry(
            btn_row_x - group_pad,
            btn_row_y - group_pad,
            content_right - btn_row_x + 2 * group_pad,
            btn_h + 2 * group_pad,
        )
        self._buttons["prog_select"].move(bx + 24 - 4, btn_row_y)

        key_x, key_y = int(0.015 * w), int(0.44 * h)
        key_w = int(0.97 * w)
        key_h = int(0.545 * h)
        white_rects, black_rects = compute_keybed_rects(key_w, key_h)
        white_semitones = [i for i in range(NUM_KEYS) if not is_black_key(i)]
        black_semitones = [i for i in range(NUM_KEYS) if is_black_key(i)]
        white_bg, white_border = _KEY_COLORS[self._dark]["white"]
        black_bg, black_border = _KEY_COLORS[self._dark]["black"]
        for semitone, rect in zip(white_semitones, white_rects):
            key = self._keys[semitone]
            key.setGeometry(rect.translated(key_x, key_y))
            key.setStyleSheet(f"QFrame {{ background: {white_bg}; border: 1px solid {white_border}; }}")
            key.raise_()
        for semitone, rect in zip(black_semitones, black_rects):
            key = self._keys[semitone]
            key.setGeometry(rect.translated(key_x, key_y))
            key.setStyleSheet(f"QFrame {{ background: {black_bg}; border: 1px solid {black_border}; }}")
            key.raise_()  # black keys sit visually on top of the white keys they overlap
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: all pre-existing tests pass (this task adds no new pytest tests - `expanded_view.py` has no pytest coverage by project convention; this confirms the rewrite didn't break `keybed.py`/`scaling.py`/`joystick_geometry.py`/`knob_geometry.py`/`accent.py` imports or any other module that depends on this file's public shapes).

- [ ] **Step 3: Verify via an off-screen smoke script**

Create a temporary script (not committed) at, e.g., `C:\Users\ehdck\AppData\Local\Temp\claude\C--DC-DD\acaa9204-6cf7-426b-a5b3-69afb2f65a1b\scratchpad\design_smoke.py`:

```python
import sys
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "C:/DC/DD/mpk-deck/src")
from mpk_deck.ui.expanded_view import ExpandedView

app = QApplication(sys.argv)
view = ExpandedView()
view.resize(960, 568)
view.show()
app.processEvents()

# Bug-fix check: joystick handle must actually be a QFrame with WA_StyledBackground set.
from PySide6.QtCore import Qt
assert view._joystick.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
assert view._joystick._handle.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
print("joystick WA_StyledBackground: OK (both outer and handle)")

# Knob style + value plumbing.
view.set_knob_style("A")
view.set_knob_value("knob_1", 0.0)
assert view._knobs["knob_1"]._value == 0.0
view.set_knob_value("knob_1", 1.0)
assert view._knobs["knob_1"]._value == 1.0
view.set_knob_style("B")
assert view._knobs["knob_1"]._style == "B"
print("knob style/value plumbing: OK")

# Accent flow-through - pick a non-default accent and confirm it lands on a pad's glow.
view.set_accent("#7c5cff")
assert view._pads["pad_1"]._accent_hex == "#7c5cff"
assert view._accent_hex == "#7c5cff"
print("accent flow-through: OK")

pix = view.grab()
out = "C:/Users/ehdck/AppData/Local/Temp/claude/C--DC-DD/acaa9204-6cf7-426b-a5b3-69afb2f65a1b/scratchpad/expanded_view_redesign.png"
pix.save(out)
print("saved", out)

view.close()
print("ALL OK")
```

Run: `python <path-to-script>`
Expected: prints each `OK` line, ends with `ALL OK`, no assertion error, no crash. Read the saved
screenshot and visually confirm: the joystick base and handle are circular (not square), the knobs
show style-B needles (since the script leaves style set to `"B"` at the end), and the base disc/handle
have a visible gradient rather than a flat fill.

- [ ] **Step 4: Commit**

```bash
git add src/mpk_deck/ui/expanded_view.py
git commit -m "fix: JoystickWidget WA_StyledBackground bug + gradient redesign; add KnobWidget"
git push
```

---

### Task 7: `ui/action_config_dialog.py` — accent-aware dialog styling

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ActionConfigDialog.__init__` gains a new keyword parameter `accent_hex: str = ACCENT_HEX`. Used by Task 8.

- [ ] **Step 1: Convert `DIALOG_QSS` from a module constant to a function**

Replace:

```python
DIALOG_QSS = f"""
QDialog {{ background: #1c1e26; }}
QLabel {{ color: #f2f4f8; font-size: 12px; }}
QLabel#heading {{ font-size: 14px; font-weight: 600; }}
QLabel#nlError {{ color: #ff6b6b; font-size: 11px; }}
QListWidget {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 8px;
    color: #f2f4f8;
    font-size: 12px;
    outline: none;
}}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT_HEX}; color: white; }}
QListWidget::item:hover:!selected {{ background: #2c2e38; }}
QLineEdit {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 8px;
    font-size: 12px;
}}
QPushButton {{
    background: #2c2e38;
    border: 1px solid #3a3c47;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{ background: #363844; }}
QPushButton#primary {{ background: {ACCENT_HEX}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #4b7bf5; }}
"""
```

with:

```python
def _dialog_qss(accent_hex: str) -> str:
    return f"""
QDialog {{ background: #1c1e26; }}
QLabel {{ color: #f2f4f8; font-size: 12px; }}
QLabel#heading {{ font-size: 14px; font-weight: 600; }}
QLabel#nlError {{ color: #ff6b6b; font-size: 11px; }}
QListWidget {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 8px;
    color: #f2f4f8;
    font-size: 12px;
    outline: none;
}}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {accent_hex}; color: white; }}
QListWidget::item:hover:!selected {{ background: #2c2e38; }}
QLineEdit {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 8px;
    font-size: 12px;
}}
QPushButton {{
    background: #2c2e38;
    border: 1px solid #3a3c47;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{ background: #363844; }}
QPushButton#primary {{ background: {accent_hex}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #4b7bf5; }}
"""
```

- [ ] **Step 2: Add the `accent_hex` constructor parameter**

Replace:

```python
    def __init__(
        self,
        control: str,
        existing: Binding | None = None,
        parent: QWidget | None = None,
        bank_names: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure {control}")
        self.setMinimumSize(480, 320)
        self.setStyleSheet(DIALOG_QSS)
```

with:

```python
    def __init__(
        self,
        control: str,
        existing: Binding | None = None,
        parent: QWidget | None = None,
        bank_names: dict[str, str] | None = None,
        accent_hex: str = ACCENT_HEX,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure {control}")
        self.setMinimumSize(480, 320)
        self.setStyleSheet(_dialog_qss(accent_hex))
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `python -c "from mpk_deck.ui.action_config_dialog import ActionConfigDialog; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 4: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py
git commit -m "feat: make ActionConfigDialog's accent color configurable"
git push
```

---

### Task 8: `MainWindow` — wire settings, Design menu, knob value routing

**Files:**
- Modify: `src/mpk_deck/ui/main_window.py`

**Interfaces:**
- Consumes: `load_last_accent`/`save_last_accent`/`load_last_knob_style`/`save_last_knob_style` (Task 3), `BankIndicator.set_accent` (Task 4), `MiniView.set_accent` (Task 5), `ExpandedView.set_accent`/`set_knob_style`/`set_knob_value` (Task 6), `ActionConfigDialog(..., accent_hex=...)` (Task 7), `ACCENT_CHOICES` (Task 1).
- Produces: no new public interface — composition root wiring only.

- [ ] **Step 1: Update imports**

Replace:

```python
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

from mpk_deck.config import (
    ACCENT_HEX,
    DEFAULT_ACTIONS_PATH,
    load_last_always_on_top,
    load_last_mode,
    load_last_theme,
    save_last_always_on_top,
    save_last_mode,
    save_last_theme,
)
```

with:

```python
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

from mpk_deck.config import (
    ACCENT_HEX,
    DEFAULT_ACTIONS_PATH,
    load_last_accent,
    load_last_always_on_top,
    load_last_knob_style,
    load_last_mode,
    load_last_theme,
    save_last_accent,
    save_last_always_on_top,
    save_last_knob_style,
    save_last_mode,
    save_last_theme,
)
from mpk_deck.ui.accent import ACCENT_CHOICES
```

(`QActionGroup` lives in `PySide6.QtGui` in this PySide6 version, not `QtWidgets` — verified directly
against the installed package; `from PySide6.QtWidgets import QActionGroup` raises `ImportError`.)

- [ ] **Step 2: Add the accent-swatch icon helper**

Add this function right after `_tray_icon()`:

```python
def _accent_icon(hex_color: str) -> QIcon:
    """A small solid-color circle, shown next to each accent choice in the Design menu."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(hex_color))
    painter.drawEllipse(1, 1, 14, 14)
    painter.end()
    return QIcon(pixmap)
```

- [ ] **Step 3: Load the two new settings in `__init__`**

Replace:

```python
        self._config = load_config(DEFAULT_ACTIONS_PATH)
        self._bank_names: dict[str, str] = {bank_id: bank.name for bank_id, bank in self._config.banks.items()}
        self._joystick_values: dict[str, float] = {"joystick_x": 0.0, "joystick_y": 0.0}
        self._engine = build_action_engine(self._config, self._on_bank_changed, self._on_joystick_continuous)
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
        self._accent_hex = load_last_accent()
        self._knob_style = load_last_knob_style()
```

- [ ] **Step 4: Apply the loaded design settings to every view at startup**

Replace:

```python
        self._mode = load_last_mode()
        self._theme = load_last_theme()
        self._always_on_top = load_last_always_on_top()
        self._apply_mode()
        self._apply_theme()
        self._apply_always_on_top()
```

with:

```python
        self._mode = load_last_mode()
        self._theme = load_last_theme()
        self._always_on_top = load_last_always_on_top()
        self._apply_mode()
        self._apply_theme()
        self._apply_always_on_top()
        self._apply_design()
```

- [ ] **Step 5: Add `_apply_design`, `_set_accent`, `_set_knob_style`**

Add these methods to `MainWindow` (e.g. right after `_apply_theme`):

```python
    def _apply_design(self) -> None:
        self._mini_view.set_accent(self._accent_hex)
        self._expanded_view.set_accent(self._accent_hex)
        self._expanded_view.set_knob_style(self._knob_style)
        self._bank_indicator.set_accent(self._accent_hex)

    def _set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        save_last_accent(accent_hex)
        self._apply_design()

    def _set_knob_style(self, style: str) -> None:
        self._knob_style = style
        save_last_knob_style(style)
        self._apply_design()
```

- [ ] **Step 6: Replace `_apply_theme`'s `set_dark` call to `BankIndicator`**

`BankIndicator` no longer has `set_dark` (Task 4 removed it — it's now theme-independent). Replace:

```python
    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)
        self._bank_indicator.set_dark(dark)
```

with:

```python
    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)
```

- [ ] **Step 7: Add the "Design" submenu to `_build_tray`**

Replace:

```python
        menu.addSeparator()
        always_on_top_action = menu.addAction("Always on Top")
        always_on_top_action.setCheckable(True)
        always_on_top_action.setChecked(self._always_on_top)
        always_on_top_action.triggered.connect(self._toggle_always_on_top)
        self._always_on_top_action = always_on_top_action

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)
```

with:

```python
        menu.addSeparator()
        always_on_top_action = menu.addAction("Always on Top")
        always_on_top_action.setCheckable(True)
        always_on_top_action.setChecked(self._always_on_top)
        always_on_top_action.triggered.connect(self._toggle_always_on_top)
        self._always_on_top_action = always_on_top_action

        menu.addSeparator()
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

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)
```

- [ ] **Step 8: Route knob continuous values into `ExpandedView`**

Replace:

```python
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
```

with:

```python
    def _apply_joystick_continuous(self, control: str, value: float) -> None:
        if control in self._joystick_values:
            self._joystick_values[control] = value
            self._expanded_view.set_joystick_deflection(
                self._joystick_values["joystick_x"], self._joystick_values["joystick_y"]
            )
            any_active = any(v != 0.0 for v in self._joystick_values.values())
            if any_active and not self._joystick_timer.isActive():
                self._joystick_timer.start(JOYSTICK_TIMER_INTERVAL_MS)
            elif not any_active and self._joystick_timer.isActive():
                self._joystick_timer.stop()
        elif control.startswith("knob_"):
            self._expanded_view.set_knob_value(control, value)
```

(The method name stays `_apply_joystick_continuous` — renaming it is out of scope for this plan; it
already means "a continuous value arrived, mirror it visually," and knobs are just another branch of
that same responsibility, matching the design spec's own framing.)

- [ ] **Step 9: Pass the current accent into `ActionConfigDialog`**

Replace:

```python
        dialog = ActionConfigDialog(control, existing, parent=self, bank_names=self._bank_names)
```

with:

```python
        dialog = ActionConfigDialog(control, existing, parent=self, bank_names=self._bank_names, accent_hex=self._accent_hex)
```

- [ ] **Step 10: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (this task adds no new pytest tests — `main_window.py` has no pytest coverage
by project convention; this confirms nothing else broke from the import/signature changes).

- [ ] **Step 11: Manually verify — Design menu changes persist**

Run: `python -m mpk_deck`. Right-click, open Design, pick a non-default accent (e.g. Violet) and knob
style B. Expected: the bank badge, joystick, knob needles, and pad-press glow all switch to the new
accent immediately; knobs show needles with no numbers. Right-click again — the picked accent/style
show as checked, everything else in the submenu unchecked. Quit via tray Quit, relaunch — expected: the
same accent and knob style are still active (persisted).

- [ ] **Step 12: Manually verify — knob values move live (if the MPK mini MK2 is connected)**

With the device plugged in, turn a physical knob. Expected: the corresponding on-screen knob's
indicator (tick or needle, per the selected style) rotates smoothly between 7 o'clock and 5 o'clock as
the knob turns, and the bound action (e.g. `set_system_volume` on `knob_1` in the current
`config/actions.yaml`) still fires exactly as before — this plan only adds a visual mirror, it doesn't
change dispatch.

- [ ] **Step 13: Commit**

```bash
git add src/mpk_deck/ui/main_window.py
git commit -m "feat: wire accent color and knob style settings into MainWindow's Design menu"
git push
```

---

### Task 9: Docs

**Files:**
- Modify: `mpk-deck/CLAUDE.md`
- Modify: `C:\DC\DD\ROADMAP.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `mpk-deck/CLAUDE.md`**

Add a short entry (this sub-project isn't part of the original A-F "다음 라운드" list — it was an
ad-hoc insertion between sub-project C's Task 8 and Task 9, triggered by two live bugs found during
C's own work) noting: `BankIndicator` is now an opaque accent badge (no more `set_dark`, only
`set_accent`); `JoystickWidget`'s `WA_StyledBackground` bug is fixed and its base/handle now use
gradient styling; knobs are a new `KnobWidget(QFrame)` with two selectable real-time value-indicator
styles (`"A"`/`"B"`); accent color (7 choices) and knob style are both persisted `QSettings` and
exposed from the tray context menu's new "Design" submenu; the keybed's black-key border deliberately
stays wired to the literal `config.ACCENT_RGB` constant, unaffected by the new setting. Update the
"실제 아키텍처" section's `ui/mini_view.py`/`ui/expanded_view.py`/`ui/bank_indicator.py` descriptions
to mention `set_accent`, `ui/accent.py`, and `ui/knob_geometry.py`. Link to
`docs/superpowers/specs/2026-08-29-design-preferences.md` and this plan file.

- [ ] **Step 2: Update `C:\DC\DD\ROADMAP.md`**

Add a Decision Log entry dated with today's date describing this ad-hoc sub-project: how it started
(two live bugs found while testing sub-project C), what it grew into (persisted accent/knob-style
settings), and any deviations from the spec discovered during implementation (if none, say so
explicitly).

- [ ] **Step 3: Commit**

```bash
git add "C:\DC\DD\mpk-deck\CLAUDE.md" "C:\DC\DD\ROADMAP.md"
git commit -m "docs: record design preferences (accent color + knob style) landing"
git push
```

## Post-Plan Checklist

- [ ] Run the full suite once more: `pytest -v` — all tests (Tasks 1-3's new ones, plus every
  pre-existing test) should pass.
- [ ] `grep -rn "set_dark" src/mpk_deck/ui/bank_indicator.py` returns nothing (fully removed, per
  Task 4).
- [ ] `python -m mpk_deck` still launches cleanly with the real `config/actions.yaml`, and the tray
  Quit still fully terminates the process (unaffected by this plan, worth re-confirming since
  `MainWindow.__init__` changed).
- [ ] Confirm no scratch smoke-test script from Task 6 Step 4 was accidentally committed: `git status`.
- [ ] Resume sub-project C: dispatch the paused Task 8 review (diff already generated at
  `.superpowers/sdd/2026-08-28-joystick-scroll/review-827139b..cd0e18f.diff`), then Task 9 (docs).
