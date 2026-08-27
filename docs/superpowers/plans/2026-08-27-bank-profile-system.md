# Bank/Profile System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `config/actions.yaml`'s single flat binding map with multiple named, switchable "banks" of bindings, switchable from any control via a new `switch_bank` action, shown identically in `MiniView` and `ExpandedView`.

**Architecture:** `core/action_registry.py` gains `Bank`/`DeckConfig` data types and `load_config`/`save_config` (replacing `load_bindings`/`save_bindings`), including migration of the old flat format. `core/action_engine.py` gains bank-awareness: `load_banks()` replaces `load_bindings()`, and `trigger()` special-cases the `switch_bank` action by calling the engine's own `switch_bank()` directly rather than dispatching to a registered handler — it's engine-intrinsic state, not a device action. `ui/action_config_dialog.py` gets a new "Add Bank" action choice that creates a bank and permanently locks the control to it. A new `ui/bank_indicator.py` widget (same floating-overlay pattern as sub-project A's `MidiStatusDot`) shows the active bank's name in both view modes.

**Tech Stack:** No new dependencies — same PySide6/PyYAML stack as the rest of the app.

**Spec:** `docs/superpowers/specs/2026-08-27-bank-profile-system-design.md`

## Global Constraints

- `switch_bank` bindings are **global** — one `control -> bank_id` map (`switch_bindings`) that applies no matter which bank is currently active. They are never stored inside a bank's own `bindings` list.
- Bank `bank_a` (display name `"Home"`) always exists and is the default `active_bank` on first run / for a missing config file. `key_0` (the keybed's leftmost key) is fixed to `switch_bindings: {key_0: bank_a}` by default.
- A control already in `switch_bindings` can never be reassigned to a different action or a different target bank through `ActionConfigDialog` — only the target bank's *name* can be edited from that control's dialog.
- `ActionEngine` stays a plain Python class with zero Qt dependency — bank-change notification is a plain injected callback (`on_bank_changed`), not a Qt signal.
- `switch_bank` is never registered in `handlers.py` — `ActionEngine.trigger()` recognizes the action name directly and calls its own `switch_bank()` method.
- `core/action_registry.py`, `core/action_engine.py`: pytest-covered (TDD). `ui/*.py`: not pytest-covered per this repo's documented policy (`mpk-deck/CLAUDE.md`) — verify manually via `python -m mpk_deck` or an off-screen smoke script.
- No git worktree — commit and push directly to `main` after each task (solo project, standing authorization per `mpk-deck/CLAUDE.md`, established 2026-08-19).

---

### Task 1: `Bank`/`DeckConfig` data types + `generate_bank_id`

**Files:**
- Modify: `src/mpk_deck/core/action_registry.py`
- Test: `tests/core/test_action_registry.py`

**Interfaces:**
- Consumes: `Binding` (already defined in this file, unchanged).
- Produces: `Bank` (dataclass: `name: str`, `bindings: list[Binding] = field(default_factory=list)`), `DeckConfig` (dataclass: `active_bank: str`, `switch_bindings: dict[str, str]`, `banks: dict[str, Bank]`), `generate_bank_id(name: str, existing_ids: Iterable[str]) -> str`, and constants `DEFAULT_BANK_ID = "bank_a"`, `DEFAULT_BANK_NAME = "Home"`, `DEFAULT_SWITCH_CONTROL = "key_0"`.

- [ ] **Step 1: Write the failing tests**

Add to the top of `tests/core/test_action_registry.py` (keep the existing `Binding`-only tests below for now — Task 2 replaces them):

```python
from mpk_deck.core.action_registry import generate_bank_id


def test_generate_bank_id_slugifies_name():
    assert generate_bank_id("Trading", existing_ids=[]) == "trading"


def test_generate_bank_id_replaces_non_alnum_with_underscore():
    assert generate_bank_id("My Cool Bank!", existing_ids=[]) == "my_cool_bank"


def test_generate_bank_id_dedupes_on_collision():
    assert generate_bank_id("Trading", existing_ids=["trading"]) == "trading_2"
    assert generate_bank_id("Trading", existing_ids=["trading", "trading_2"]) == "trading_3"


def test_generate_bank_id_blank_name_falls_back_to_bank():
    assert generate_bank_id("   ", existing_ids=[]) == "bank"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_action_registry.py -k generate_bank_id -v`
Expected: FAIL with `ImportError: cannot import name 'generate_bank_id'`

- [ ] **Step 3: Add the data types and function**

In `src/mpk_deck/core/action_registry.py`, add `import re` to the top imports, then add (after the `Binding` dataclass, before `ActionConfigError`):

```python
DEFAULT_BANK_ID = "bank_a"
DEFAULT_BANK_NAME = "Home"
DEFAULT_SWITCH_CONTROL = "key_0"


@dataclass
class Bank:
    name: str
    bindings: list[Binding] = field(default_factory=list)


@dataclass
class DeckConfig:
    active_bank: str
    switch_bindings: dict[str, str]
    banks: dict[str, Bank]


def generate_bank_id(name: str, existing_ids) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "bank"
    existing = set(existing_ids)
    candidate = slug
    n = 2
    while candidate in existing:
        candidate = f"{slug}_{n}"
        n += 1
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_action_registry.py -k generate_bank_id -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/action_registry.py tests/core/test_action_registry.py
git commit -m "feat: add Bank/DeckConfig types and generate_bank_id"
git push
```

---

### Task 2: `load_config`/`save_config` — new format, migration, default seed

**Files:**
- Modify: `src/mpk_deck/core/action_registry.py`
- Modify: `tests/core/test_action_registry.py` (replaces the old `load_bindings`/`save_bindings` tests)

**Interfaces:**
- Consumes: `Bank`, `DeckConfig`, `Binding`, `DEFAULT_BANK_ID`, `DEFAULT_BANK_NAME`, `DEFAULT_SWITCH_CONTROL` (Task 1).
- Produces: `load_config(path: str | Path) -> DeckConfig` (never raises — missing file, empty file, and malformed YAML all fall back to a default single-bank config), `save_config(path: str | Path, config: DeckConfig) -> None`. Removes `load_bindings`, `save_bindings`, `ActionConfigError` (dead once `load_config` no longer raises on a missing file).

- [ ] **Step 1: Replace the whole test file**

Replace the entire contents of `tests/core/test_action_registry.py` with:

```python
from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    DEFAULT_BANK_ID,
    DEFAULT_BANK_NAME,
    DEFAULT_SWITCH_CONTROL,
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


def test_load_config_missing_file_returns_default_seed(tmp_path):
    config = load_config(tmp_path / "nope.yaml")
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])}


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
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"})
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
    bindings = config.banks[DEFAULT_BANK_ID].bindings
    assert len(bindings) == 1
    assert bindings[0].control == "pad_2"


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
    assert config.banks["bank_a"] == Bank(name="Home", bindings=[])
    assert config.banks["bank_b"].name == "Trading"
    assert config.banks["bank_b"].bindings == [
        Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://example.com"})
    ]


def test_save_then_load_round_trips_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    config = DeckConfig(
        active_bank="bank_b",
        switch_bindings={"key_0": "bank_a"},
        banks={
            "bank_a": Bank(name="Home", bindings=[]),
            "bank_b": Bank(
                name="Trading",
                bindings=[
                    Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://x.com"})
                ],
            ),
        },
    )
    save_config(path, config)
    assert load_config(path) == config
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_action_registry.py -v`
Expected: the `generate_bank_id` tests still pass (Task 1); every `load_config`/`save_config` test FAILs with `ImportError: cannot import name 'load_config'`

- [ ] **Step 3: Replace `load_bindings`/`save_bindings`/`ActionConfigError` with `load_config`/`save_config`**

In `src/mpk_deck/core/action_registry.py`, add `import yaml` is already present; add `import logging` is already present. Delete the `ActionConfigError` class, `load_bindings`, and `save_bindings` functions entirely, and replace them with:

```python
def _parse_bindings_list(raw_bindings: list) -> list[Binding]:
    bindings: list[Binding] = []
    for i, entry in enumerate(raw_bindings):
        try:
            bindings.append(_parse_binding(entry))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("skipping invalid binding at index %d: %s", i, exc)
    return bindings


def _default_config() -> DeckConfig:
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])},
    )


def load_config(path: str | Path) -> DeckConfig:
    path = Path(path)
    if not path.exists():
        return _default_config()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        logger.warning("failed to parse %s, starting with defaults", path)
        return _default_config()

    if "banks" in data:
        banks = {}
        for bank_id, bank_data in (data.get("banks") or {}).items():
            raw_bindings = bank_data.get("bindings", []) or []
            banks[bank_id] = Bank(name=bank_data.get("name", bank_id), bindings=_parse_bindings_list(raw_bindings))
        return DeckConfig(
            active_bank=data.get("active_bank") or DEFAULT_BANK_ID,
            switch_bindings=dict(data.get("switch_bindings") or {}),
            banks=banks,
        )

    # old flat format (or an empty/near-empty file) -> migrate
    raw_bindings = data.get("bindings", []) or []
    bindings = _parse_bindings_list(raw_bindings)
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=bindings)},
    )


def save_config(path: str | Path, config: DeckConfig) -> None:
    path = Path(path)
    data = {
        "active_bank": config.active_bank,
        "switch_bindings": config.switch_bindings,
        "banks": {
            bank_id: {"name": bank.name, "bindings": [asdict(b) for b in bank.bindings]}
            for bank_id, bank in config.banks.items()
        },
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
```

`_parse_binding` (the single-entry parser) is unchanged — leave it exactly as-is.

- [ ] **Step 4: Check for other usages of the removed names before running tests**

Run: `grep -rn "load_bindings\|save_bindings\|ActionConfigError" src/ tests/`
Expected: no matches outside `src/mpk_deck/ui/main_window.py` (fixed in Task 6) — if anything else matches, note it, it'll need the same treatment as Task 6 applies to `main_window.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_action_registry.py -v`
Expected: 12 passed

Note: `pytest -q` (the whole suite) will fail at this point — `main_window.py` still imports the now-deleted `load_bindings`/`save_bindings`. That's expected and fixed in Task 6; don't try to fix it here.

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/core/action_registry.py tests/core/test_action_registry.py
git commit -m "feat: replace load_bindings/save_bindings with bank-aware load_config/save_config"
git push
```

---

### Task 3: `ActionEngine` — bank-aware loading, `switch_bank`, `trigger()` dispatch

**Files:**
- Modify: `src/mpk_deck/core/action_engine.py`
- Modify: `tests/core/test_action_engine.py`

**Interfaces:**
- Consumes: `Binding` (`mpk_deck.core.action_registry`).
- Produces: `ActionEngine(on_bank_changed: Callable[[str], None] | None = None)`, `load_banks(banks: dict[str, list[Binding]], switch_bindings: dict[str, str], active_bank: str) -> None` (replaces `load_bindings`), `switch_bank(bank_id: str) -> None`, `active_bank` property (`str`). `trigger`, `set_continuous`, `bindings`, `register_trigger`, `register_continuous` keep their existing signatures.

- [ ] **Step 1: Replace the test file**

Replace the entire contents of `tests/core/test_action_engine.py` with:

```python
from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Binding


def test_trigger_calls_registered_handler_with_params():
    engine = ActionEngine()
    calls = []
    engine.register_trigger("launch_program", lambda params: calls.append(params))
    engine.load_banks(
        {"bank_a": [Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "x"})]},
        switch_bindings={},
        active_bank="bank_a",
    )

    engine.trigger("pad_1")

    assert calls == [{"path": "x"}]


def test_trigger_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.trigger("pad_99")


def test_trigger_unregistered_action_does_not_raise():
    engine = ActionEngine()
    engine.load_banks(
        {"bank_a": [Binding(control="pad_1", type="trigger", action="nope", params={})]},
        switch_bindings={},
        active_bank="bank_a",
    )
    engine.trigger("pad_1")


def test_set_continuous_calls_handler_with_value():
    engine = ActionEngine()
    calls = []
    engine.register_continuous("set_system_volume", lambda params, value: calls.append((params, value)))
    engine.load_banks(
        {"bank_a": [Binding(control="knob_1", type="continuous", action="set_system_volume", params={})]},
        switch_bindings={},
        active_bank="bank_a",
    )

    engine.set_continuous("knob_1", 0.5)

    assert calls == [({}, 0.5)]


def test_set_continuous_unknown_control_does_not_raise():
    engine = ActionEngine()
    engine.set_continuous("knob_99", 1.0)


def test_bindings_reflects_active_bank_only():
    engine = ActionEngine()
    engine.load_banks(
        {
            "bank_a": [Binding(control="pad_1", type="trigger", action="a", params={})],
            "bank_b": [Binding(control="pad_1", type="trigger", action="b", params={})],
        },
        switch_bindings={},
        active_bank="bank_a",
    )
    assert engine.bindings["pad_1"].action == "a"


def test_switch_bindings_always_present_regardless_of_active_bank():
    engine = ActionEngine()
    engine.load_banks({"bank_a": [], "bank_b": []}, switch_bindings={"key_0": "bank_a"}, active_bank="bank_b")
    binding = engine.bindings["key_0"]
    assert binding.action == "switch_bank"
    assert binding.params == {"bank_id": "bank_a"}


def test_trigger_on_switch_control_switches_active_bank():
    engine = ActionEngine()
    engine.load_banks(
        {
            "bank_a": [Binding(control="pad_1", type="trigger", action="a", params={})],
            "bank_b": [Binding(control="pad_1", type="trigger", action="b", params={})],
        },
        switch_bindings={"key_0": "bank_b"},
        active_bank="bank_a",
    )

    engine.trigger("key_0")

    assert engine.active_bank == "bank_b"
    assert engine.bindings["pad_1"].action == "b"


def test_switch_bank_calls_on_bank_changed_callback():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": [], "bank_b": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("bank_b")

    assert calls == ["bank_b"]


def test_switch_bank_to_same_bank_is_a_noop():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("bank_a")

    assert calls == []


def test_switch_bank_to_unknown_bank_is_ignored():
    calls = []
    engine = ActionEngine(on_bank_changed=calls.append)
    engine.load_banks({"bank_a": []}, switch_bindings={}, active_bank="bank_a")

    engine.switch_bank("does_not_exist")

    assert engine.active_bank == "bank_a"
    assert calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_action_engine.py -v`
Expected: every test FAILs — `load_banks` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Rewrite `ActionEngine`**

Replace the entire contents of `src/mpk_deck/core/action_engine.py` with:

```python
import logging
from typing import Callable, Optional

from mpk_deck.core.action_registry import Binding

logger = logging.getLogger(__name__)

TriggerHandler = Callable[[dict], None]
ContinuousHandler = Callable[[dict, float], None]


class ActionEngine:
    def __init__(self, on_bank_changed: Optional[Callable[[str], None]] = None) -> None:
        self._trigger_handlers: dict[str, TriggerHandler] = {}
        self._continuous_handlers: dict[str, ContinuousHandler] = {}
        self._bindings_by_control: dict[str, Binding] = {}
        self._banks: dict[str, list[Binding]] = {}
        self._switch_bindings: dict[str, str] = {}
        self._active_bank: str = ""
        self._on_bank_changed = on_bank_changed

    def register_trigger(self, action_name: str, handler: TriggerHandler) -> None:
        self._trigger_handlers[action_name] = handler

    def register_continuous(self, action_name: str, handler: ContinuousHandler) -> None:
        self._continuous_handlers[action_name] = handler

    def load_banks(self, banks: dict[str, list[Binding]], switch_bindings: dict[str, str], active_bank: str) -> None:
        self._banks = banks
        self._switch_bindings = switch_bindings
        self._active_bank = active_bank
        self._rebuild_bindings()

    def _rebuild_bindings(self) -> None:
        merged: dict[str, Binding] = {}
        for binding in self._banks.get(self._active_bank, []):
            merged[binding.control] = binding
        for control, bank_id in self._switch_bindings.items():
            merged[control] = Binding(control=control, type="trigger", action="switch_bank", params={"bank_id": bank_id})
        self._bindings_by_control = merged

    @property
    def bindings(self) -> dict[str, Binding]:
        return dict(self._bindings_by_control)

    @property
    def active_bank(self) -> str:
        return self._active_bank

    def switch_bank(self, bank_id: str) -> None:
        if bank_id not in self._banks or bank_id == self._active_bank:
            return
        self._active_bank = bank_id
        self._rebuild_bindings()
        if self._on_bank_changed is not None:
            self._on_bank_changed(bank_id)

    def trigger(self, control: str) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            logger.info("no binding for control %s", control)
            return
        if binding.action == "switch_bank":
            self.switch_bank(binding.params["bank_id"])
            return
        handler = self._trigger_handlers.get(binding.action)
        if handler is None:
            logger.warning("no trigger handler registered for action %s", binding.action)
            return
        handler(binding.params)

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_action_engine.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/action_engine.py tests/core/test_action_engine.py
git commit -m "feat: add bank-aware load_banks/switch_bank to ActionEngine"
git push
```

---

### Task 4: `ui/bank_indicator.py` — bank name display widget

**Files:**
- Create: `src/mpk_deck/ui/bank_indicator.py`

**Interfaces:**
- Produces: `BankIndicator(QLabel)` with `set_bank_name(name: str) -> None` and `set_dark(dark: bool) -> None`. No pytest coverage (Qt widget, per project policy) — verified in Task 6's manual check.

- [ ] **Step 1: Write the widget**

```python
# src/mpk_deck/ui/bank_indicator.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

_LIGHT_TEXT = "#23242b"
_DARK_TEXT = "#f2f4f8"


class BankIndicator(QLabel):
    """Shows the active bank's display name. Theme-aware text color, purely informational."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dark = False
        self.set_bank_name("")
        self._apply_style()

    def set_bank_name(self, name: str) -> None:
        self.setText(name)
        self.adjustSize()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._apply_style()

    def _apply_style(self) -> None:
        color = _DARK_TEXT if self._dark else _LIGHT_TEXT
        self.setStyleSheet(
            f"QLabel {{ color: {color}; font-size: 11px; font-weight: 600; background: transparent; }}"
        )
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from mpk_deck.ui.bank_indicator import BankIndicator; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 3: Commit**

```bash
git add src/mpk_deck/ui/bank_indicator.py
git commit -m "feat: add BankIndicator widget"
git push
```

---

### Task 5: `ActionConfigDialog` — "Add Bank" flow + locking

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`

**Interfaces:**
- Consumes: nothing new from other modules.
- Produces: `ActionConfigDialog(control, existing=None, parent=None, bank_names: dict[str, str] | None = None)` — new optional `bank_names` keyword param. New method `result_bank_name() -> str`. `result_binding()` for the `switch_bank` action now returns a `Binding` with empty `params` (the caller, `MainWindow` in Task 6, fills in the real `bank_id`). No pytest coverage (Qt widget) — verified in Task 6's manual check.

- [ ] **Step 1: Add the new action choice**

In `src/mpk_deck/ui/action_config_dialog.py`, change:

```python
ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
]
ACTION_GLYPHS = {name: glyph for name, glyph, _ in ACTION_CHOICES}
ACTION_LABELS = {name: label for name, _, label in ACTION_CHOICES}
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
}
```

to:

```python
ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
    ("switch_bank", "\u2795", "Add Bank"),
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

- [ ] **Step 2: Add the `bank_names` constructor param and lock-state tracking**

Change the `__init__` signature:

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
        self._control = control
        self._bank_names = bank_names or {}
        self._locked = existing is not None and existing.action == "switch_bank"
```

(This replaces the existing first few lines of `__init__` up through `self._control = control` — everything after `self._control = control` in the current file stays as-is until the point covered by the next step.)

- [ ] **Step 3: Add the bank-name param page**

Right after the existing line `self._volume_page = self._build_volume_page()`, add:

```python
        self._bank_name_edit = self._build_bank_name_page()
```

Add the new page-builder method anywhere among the other `_build_*_page` methods (e.g. right after `_build_volume_page`):

```python
    def _build_bank_name_page(self) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(page)
        edit.setPlaceholderText("Bank name")
        layout.addWidget(edit)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit
```

- [ ] **Step 4: Update `_apply_binding` for the switch_bank case, and lock the list when applicable**

Replace:

```python
    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
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
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))

    def _lock_to_switch_bank(self) -> None:
        for i in range(self._action_list.count()):
            item = self._action_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) != "switch_bank":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
```

Then, at the end of `__init__`, change:

```python
        if existing is not None:
            self._apply_binding(existing)
        else:
            self._select_action(ACTION_CHOICES[0][0])
```

to:

```python
        if existing is not None:
            self._apply_binding(existing)
        else:
            self._select_action(ACTION_CHOICES[0][0])
        if self._locked:
            self._lock_to_switch_bank()
```

- [ ] **Step 5: Add `result_bank_name()` and fix `result_binding()` for switch_bank**

Replace:

```python
    def result_binding(self) -> Binding:
        action = self._current_action()
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text()} if key and edit else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)
```

with:

```python
    def result_binding(self) -> Binding:
        action = self._current_action()
        if action == "switch_bank":
            # The real bank_id is assigned by the caller (new bank, or the existing
            # locked control's target) - this dialog only ever supplies the name.
            return Binding(control=self._control, type="trigger", action="switch_bank", params={})
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text()} if key and edit else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)

    def result_bank_name(self) -> str:
        return self._bank_name_edit.text().strip()
```

- [ ] **Step 6: Verify it imports cleanly**

Run: `python -c "from mpk_deck.ui.action_config_dialog import ActionConfigDialog; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 7: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py
git commit -m "feat: add Add Bank flow and switch_bank locking to ActionConfigDialog"
git push
```

---

### Task 6: `MainWindow` — wire banks end-to-end

**Files:**
- Modify: `src/mpk_deck/ui/main_window.py`

**Interfaces:**
- Consumes: `Bank`, `DeckConfig`, `generate_bank_id`, `load_config`, `save_config` (Task 2), `ActionEngine(on_bank_changed=...)`/`load_banks`/`active_bank` (Task 3), `BankIndicator` (Task 4), `ActionConfigDialog(..., bank_names=...)`/`result_bank_name()` (Task 5).
- Produces: no new public interface — this is the app's own composition root.

- [ ] **Step 1: Update imports**

Replace:

```python
from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Binding, load_bindings, save_bindings
from mpk_deck.core.handlers import focus_window, launch_program, open_url, set_system_volume
from mpk_deck.midi.mpk_controller import MPKController
from mpk_deck.ui.action_config_dialog import ActionConfigDialog
from mpk_deck.ui.expanded_view import ExpandedView
from mpk_deck.ui.midi_status_dot import MidiStatusDot
from mpk_deck.ui.mini_view import MiniView
```

with:

```python
from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Bank, Binding, DeckConfig, generate_bank_id, load_config, save_config
from mpk_deck.core.handlers import focus_window, launch_program, open_url, set_system_volume
from mpk_deck.midi.mpk_controller import MPKController
from mpk_deck.ui.action_config_dialog import ActionConfigDialog
from mpk_deck.ui.bank_indicator import BankIndicator
from mpk_deck.ui.expanded_view import ExpandedView
from mpk_deck.ui.midi_status_dot import MidiStatusDot
from mpk_deck.ui.mini_view import MiniView
```

- [ ] **Step 2: Replace `build_action_engine`**

Replace:

```python
def build_action_engine() -> ActionEngine:
    engine = ActionEngine()
    engine.register_trigger("launch_program", launch_program)
    engine.register_trigger("open_url", open_url)
    engine.register_trigger("focus_window", focus_window)
    engine.register_continuous("set_system_volume", set_system_volume)
    try:
        bindings = load_bindings(DEFAULT_ACTIONS_PATH)
    except Exception:
        logger.exception("failed to load %s, starting with no bindings", DEFAULT_ACTIONS_PATH)
        bindings = []
    engine.load_bindings(bindings)
    return engine
```

with:

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

(`load_config` no longer raises, so the try/except is gone — `load_config` itself already falls back to a default config on any load failure, per Task 2.)

- [ ] **Step 3: Update `__init__`'s engine/state construction**

Replace:

```python
        self._engine = build_action_engine()
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False

        self._midi = MPKController(self._engine)
        self._midi_detected = self._midi.start()

        self._midi_status_dot = MidiStatusDot(self)
        self._midi_status_dot.set_connected(self._midi_detected)
        self._midi_status_dot.retry_requested.connect(self._poll_midi)
        self._midi_timer = QTimer(self)
        self._midi_timer.timeout.connect(self._poll_midi)
        self._midi_timer.start(MIDI_POLL_INTERVAL_MS)
```

with:

```python
        self._config = load_config(DEFAULT_ACTIONS_PATH)
        self._bank_names: dict[str, str] = {bank_id: bank.name for bank_id, bank in self._config.banks.items()}
        self._engine = build_action_engine(self._config, self._on_bank_changed)
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False

        self._midi = MPKController(self._engine)
        self._midi_detected = self._midi.start()

        self._midi_status_dot = MidiStatusDot(self)
        self._midi_status_dot.set_connected(self._midi_detected)
        self._midi_status_dot.retry_requested.connect(self._poll_midi)
        self._midi_timer = QTimer(self)
        self._midi_timer.timeout.connect(self._poll_midi)
        self._midi_timer.start(MIDI_POLL_INTERVAL_MS)

        self._bank_indicator = BankIndicator(self)
        self._bank_indicator.set_bank_name(self._bank_names.get(self._engine.active_bank, self._engine.active_bank))
```

- [ ] **Step 4: Rename the dot-only positioning method to cover both overlay widgets**

Replace:

```python
    def _position_midi_status_dot(self) -> None:
        dot = self._midi_status_dot
        dot.move(self.width() - dot.width() - STATUS_DOT_MARGIN, self.height() - dot.height() - STATUS_DOT_MARGIN)
        dot.raise_()
```

with:

```python
    def _position_overlay_widgets(self) -> None:
        dot = self._midi_status_dot
        dot.move(self.width() - dot.width() - STATUS_DOT_MARGIN, self.height() - dot.height() - STATUS_DOT_MARGIN)
        dot.raise_()
        indicator = self._bank_indicator
        indicator.move(dot.x() - indicator.width() - STATUS_DOT_MARGIN, dot.y() + (dot.height() - indicator.height()) // 2)
        indicator.raise_()
```

Then update both call sites. In `__init__`, the line `self._position_midi_status_dot()` (the last line of `__init__`) becomes:

```python
        self._position_overlay_widgets()
```

And in `resizeEvent`:

```python
    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._enforce_aspect()
        self._position_overlay_widgets()
```

(replacing the existing `self._position_midi_status_dot()` line in that method).

- [ ] **Step 5: Wire theme changes into the bank indicator**

Replace:

```python
    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)
```

with:

```python
    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)
        self._bank_indicator.set_dark(dark)
```

- [ ] **Step 6: Add the bank-change handler and binding-save split**

Replace:

```python
    def _on_control_configure_requested(self, control: str) -> None:
        existing = self._bindings.get(control)
        dialog = ActionConfigDialog(control, existing, parent=self)
        if dialog.exec():
            binding = dialog.result_binding()
            self._bindings[control] = binding
            self._engine.load_bindings(list(self._bindings.values()))
            save_bindings(DEFAULT_ACTIONS_PATH, list(self._bindings.values()))
            self._mini_view.update_bindings(self._bindings)
```

with:

```python
    def _on_bank_changed(self, bank_id: str) -> None:
        self._bindings = dict(self._engine.bindings)
        self._mini_view.update_bindings(self._bindings)
        self._bank_indicator.set_bank_name(self._bank_names.get(bank_id, bank_id))
        self._config.active_bank = bank_id
        save_config(DEFAULT_ACTIONS_PATH, self._config)

    def _on_control_configure_requested(self, control: str) -> None:
        existing = self._bindings.get(control)
        dialog = ActionConfigDialog(control, existing, parent=self, bank_names=self._bank_names)
        if not dialog.exec():
            return
        binding = dialog.result_binding()
        if binding.action == "switch_bank":
            self._save_bank_binding(control, existing, dialog.result_bank_name())
        else:
            self._save_normal_binding(control, binding)

    def _save_bank_binding(self, control: str, existing: Binding | None, bank_name: str) -> None:
        is_new = existing is None or existing.action != "switch_bank"
        if is_new:
            bank_id = generate_bank_id(bank_name, self._config.banks.keys())
            self._config.banks[bank_id] = Bank(name=bank_name, bindings=[])
            self._config.switch_bindings[control] = bank_id
        else:
            bank_id = existing.params["bank_id"]
            self._config.banks[bank_id].name = bank_name
        self._bank_names[bank_id] = bank_name
        binding = Binding(control=control, type="trigger", action="switch_bank", params={"bank_id": bank_id})
        self._bindings[control] = binding
        self._sync_after_binding_change()

    def _save_normal_binding(self, control: str, binding: Binding) -> None:
        active_id = self._engine.active_bank
        bank = self._config.banks[active_id]
        bank.bindings = [b for b in bank.bindings if b.control != control] + [binding]
        self._bindings[control] = binding
        self._sync_after_binding_change()

    def _sync_after_binding_change(self) -> None:
        self._engine.load_banks(
            {bank_id: bank.bindings for bank_id, bank in self._config.banks.items()},
            self._config.switch_bindings,
            self._engine.active_bank,
        )
        save_config(DEFAULT_ACTIONS_PATH, self._config)
        self._mini_view.update_bindings(self._bindings)
```

- [ ] **Step 7: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (this task adds no new tests — `main_window.py` has no pytest coverage by project convention; this confirms nothing else in the suite broke from the import/rename changes).

- [ ] **Step 8: Manually verify — Add Bank flow**

Run: `python -m mpk_deck`. Double-click an unbound pad. Select "Add Bank" from the action list, type a name (e.g. "Trading"), Save. Expected: no crash; `config/actions.yaml` now contains a `banks` section with the new bank and a `switch_bindings` entry mapping that pad to it. Double-click the same pad again — expected: every action in the list except "Add Bank" is greyed out/unselectable, and the name field shows "Trading". Trigger that pad (click it once in Mini mode). Expected: the bank indicator's text changes, and any pad bound in the new (empty) bank shows as unbound (since it's a fresh bank with no bindings yet).

- [ ] **Step 9: Manually verify — persistence across restart**

Close the app via the tray Quit (confirms sub-project A's fix still works), reopen with `python -m mpk_deck`. Expected: the app reopens on whichever bank was active when it closed, and the bank indicator shows the correct name immediately.

- [ ] **Step 10: Manually verify — old-format migration**

Before this task, back up the real `config/actions.yaml` (`cp config/actions.yaml config/actions.yaml.bak` — this file predates the bank system and is in the old flat format). Run `python -m mpk_deck` once with the *backed-up* old file restored as `config/actions.yaml` (temporarily), confirm the app starts with no error and the existing pad bindings (`pad_1`, `pad_6`, `pad_7`, `knob_1` per the current file) still work exactly as before. Then let the app run through a normal Save (e.g. edit and re-save any binding) and confirm `config/actions.yaml` now contains `banks`/`switch_bindings`/`active_bank` keys. Restore the real file afterward if the temporary swap changed anything unintended.

- [ ] **Step 11: Commit**

```bash
git add src/mpk_deck/ui/main_window.py
git commit -m "feat: wire bank system into MainWindow end-to-end"
git push
```

---

### Task 7: Docs

**Files:**
- Modify: `mpk-deck/CLAUDE.md`
- Modify: `C:\DC\DD\ROADMAP.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `mpk-deck/CLAUDE.md`**

In the "다음 라운드" list, mark item **B** done (strike it like **A** was marked in the previous round's docs commit) with a short summary: bank-aware `actions.yaml` schema, `switch_bank` as an engine-intrinsic global action, "Add Bank" flow + locking in `ActionConfigDialog`, `BankIndicator` overlay. Note the migration path for old-format files. Link to `docs/superpowers/specs/2026-08-27-bank-profile-system-design.md` and this plan file.

- [ ] **Step 2: Update `C:\DC\DD\ROADMAP.md`**

Check off item **B** under mpk-deck's "다음 라운드" list (same style as how **A** was checked off), and add a Decision Log entry dated with today's date summarizing what shipped and any deviations from the spec discovered during implementation (if any — if none, say so explicitly, don't skip the entry).

- [ ] **Step 3: Commit**

```bash
git add "C:\DC\DD\mpk-deck\CLAUDE.md" "C:\DC\DD\ROADMAP.md"
git commit -m "docs: record bank/profile system landing"
git push
```

## Post-Plan Checklist

- [ ] Run the full suite once more: `pytest -v` — all tests (Tasks 1-3's new/replaced ones, plus every pre-existing test) should pass.
- [ ] `grep -rn "load_bindings\|save_bindings\|ActionConfigError\|engine.load_bindings" src/` returns nothing.
- [ ] `python -m mpk_deck` still launches cleanly with the real `config/actions.yaml` (post-migration, in the new format) and the tray Quit still fully terminates the process (sub-project A's fix, unaffected by this plan but worth re-confirming since `MainWindow.__init__` changed substantially).
- [ ] Confirm no `config/actions.yaml.bak` or other scratch file from Task 6's manual verification was accidentally committed: `git status`.
