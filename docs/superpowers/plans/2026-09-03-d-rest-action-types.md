# D-rest Action Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three new action types to mpk-deck — knob-driven display brightness, fire-and-forget shell command, and media transport keys — plus natural-language coverage for each.

**Architecture:** Each action type follows the repo's existing "add an action" recipe: a handler + injectable adapter in `core/handlers.py`, registration in `build_action_engine`, three table entries + a param page in `ui/action_config_dialog.py`, a KO label + SVG glyph in `ui/action_icons.py`, and an `ACTION_TYPE` entry + tool-schema field + `_to_binding` branch in `core/nl_action.py`. No `config/actions.yaml` schema change — just new `action` string values. All tests are pure-function / seam-injection.

**Tech Stack:** Python 3.13, PySide6, pywin32 (`win32com.client` for WMI brightness, `win32api`/`win32con` for media keys), `subprocess` (shell command), anthropic (NL), pytest.

**Spec:** `docs/superpowers/specs/2026-09-03-d-rest-action-types-design.md`

## Global Constraints

- Python >= 3.13; package manager is plain `pip` (`pip install -e ".[dev]"`), no lock file, no uv.
- No new runtime dependency. WMI brightness uses `win32com.client` (already in `pywin32`).
- Windows-only deps (`win32com`, `win32api`, `subprocess.DETACHED_PROCESS`) are lazy-imported / referenced **inside** the adapter function body so `core/handlers.py` still imports on non-Windows.
- Every adapter is an injectable seam (keyword-only arg with a `None` default that falls back to the real `_default_*` function), matching `set_system_volume(volume_setter=None)` and `scroll_*(sender=None)`.
- Handler exceptions are already caught + logged by `ActionEngine`; new handlers must never raise on bad params — log at `info` and return.
- Tests live at `tests/<mirror of src path>` (e.g. `core/handlers.py` → `tests/core/test_handlers.py`).
- Run the full suite with `pytest` from the repo root. Baseline before this plan: **271 passed**.
- Code comments, commit messages, identifiers in English. Conventional Commits.
- Korean UI strings stay Korean.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/mpk_deck/core/handlers.py` | side-effect handlers + adapters | add 3 handlers, 3 `_default_*` adapters, `_should_apply_now` throttle helper + `_LAST_APPLIED`, `_MEDIA_VK` |
| `src/mpk_deck/ui/main_window.py` | engine wiring | add 3 imports + 3 `register_*` calls in `build_action_engine` |
| `src/mpk_deck/ui/action_config_dialog.py` | binding editor dialog | `ACTION_CHOICES`/`ACTION_TYPE`/`PARAM_KEY` +3, `_add_combo_page` helper, `_media_combo`, `_page_for_action` +3, `_param_edit_for` +1, `_apply_binding` + `result_binding` media_key branch |
| `src/mpk_deck/ui/action_icons.py` | action labels + SVG glyphs | `ACTION_KO_LABEL` +3, `_ACTION_SVG` +3 (`_ACTION_SVG_KNOB` +1 for brightness) |
| `src/mpk_deck/core/nl_action.py` | NL → Binding | `ACTION_TYPE` +3, `_TOOL` schema `command` + `media_key` props, `_to_binding` +3 branches |
| `tests/core/test_handlers.py` | adapter + throttle tests | new tests |
| `tests/core/test_nl_action.py` | NL branch tests | new tests |
| `tests/ui/test_action_config_dialog.py` | page-switch + round-trip | new tests |
| `CONTEXT.md` | doc | add the 3 action types + live-verification notes |

---

## Task 1: `set_display_brightness` handler + throttle

**Files:**
- Modify: `src/mpk_deck/core/handlers.py`
- Modify: `src/mpk_deck/ui/main_window.py`
- Test: `tests/core/test_handlers.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `handlers.set_display_brightness(params: dict, value: float, *, brightness_setter=None, now: float | None = None) -> None`
  - `handlers._default_brightness_setter(percent: int) -> None`
  - `handlers._should_apply_now(key: str, min_interval_s: float, now: float) -> bool`
  - `handlers._LAST_APPLIED: dict[str, float]` (module state; tests clear it)

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_handlers.py`:

```python
def test_set_display_brightness_converts_normalized_value_to_percent(monkeypatch):
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 0.5, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, 0.0, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, 1.0, brightness_setter=calls.append, now=0.0)
    assert calls == [50, 0, 100]


def test_set_display_brightness_clamps_out_of_range(monkeypatch):
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 1.7, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, -0.3, brightness_setter=calls.append, now=0.0)
    assert calls == [100, 0]


def test_set_display_brightness_throttles_rapid_calls():
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 0.1, brightness_setter=calls.append, now=0.00)
    handlers.set_display_brightness({}, 0.2, brightness_setter=calls.append, now=0.05)  # dropped
    handlers.set_display_brightness({}, 0.3, brightness_setter=calls.append, now=0.20)  # applied
    assert calls == [10, 30]
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/core/test_handlers.py -k display_brightness -v`
Expected: FAIL — `AttributeError: module 'mpk_deck.core.handlers' has no attribute 'set_display_brightness'`

- [ ] **Step 3: Implement**

In `src/mpk_deck/core/handlers.py` add `import time` to the imports, then add:

```python
# Throttle state for continuous handlers whose side effect is expensive
# (WMI brightness is ~50-100ms/call and a knob emits tens of events/second).
# ponytail: module dict, fine for the handful of throttled controls we have.
_LAST_APPLIED: dict[str, float] = {}
_BRIGHTNESS_MIN_INTERVAL_S = 0.1  # ~10 Hz; brightness is coarse enough that a dropped tick is invisible


def _should_apply_now(key: str, min_interval_s: float, now: float) -> bool:
    last = _LAST_APPLIED.get(key)
    if last is not None and now - last < min_interval_s:
        return False
    _LAST_APPLIED[key] = now
    return True


def set_display_brightness(
    params: dict, value: float, *, brightness_setter=None, now: float | None = None
) -> None:
    """`value` is a normalized 0.0-1.0 level (knob CC, already converted by translate()).
    Throttled to ~10 Hz; intermediate values are dropped (the knob keeps sending its
    current absolute position while it turns)."""
    if not _should_apply_now(
        "brightness", _BRIGHTNESS_MIN_INTERVAL_S, now if now is not None else time.monotonic()
    ):
        return
    setter = brightness_setter or _default_brightness_setter
    setter(round(max(0.0, min(1.0, value)) * 100))


def _default_brightness_setter(percent: int) -> None:
    import win32com.client

    wmi = win32com.client.GetObject(r"winmgmts:\\.\root\WMI")
    for method in wmi.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods"):
        method.WmiSetBrightness(1, percent)  # (timeout_seconds, brightness_percent)
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/core/test_handlers.py -k display_brightness -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Register in the engine**

In `src/mpk_deck/ui/main_window.py`, add `set_display_brightness` to the `from mpk_deck.core.handlers import (...)` block, and in `build_action_engine` after the existing `register_continuous` calls add:

```python
    engine.register_continuous("set_display_brightness", set_display_brightness)
```

- [ ] **Step 6: Run the full suite**

Run: `pytest`
Expected: 274 passed (271 baseline + 3)

- [ ] **Step 7: Commit**

```bash
git add src/mpk_deck/core/handlers.py src/mpk_deck/ui/main_window.py tests/core/test_handlers.py
git commit -m "feat(core): set_display_brightness handler (WMI, throttled) + engine registration"
```

---

## Task 2: `run_shell_command` handler

**Files:**
- Modify: `src/mpk_deck/core/handlers.py`
- Modify: `src/mpk_deck/ui/main_window.py`
- Test: `tests/core/test_handlers.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `handlers.run_shell_command(params: dict, *, runner=None) -> None`
  - `handlers._default_command_runner(command: str) -> None`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_handlers.py`:

```python
def test_run_shell_command_passes_command_to_runner():
    calls = []
    handlers.run_shell_command({"command": "echo hi && dir"}, runner=calls.append)
    assert calls == ["echo hi && dir"]


def test_run_shell_command_strips_whitespace():
    calls = []
    handlers.run_shell_command({"command": "  notepad  "}, runner=calls.append)
    assert calls == ["notepad"]


def test_run_shell_command_empty_or_missing_is_noop():
    calls = []
    handlers.run_shell_command({"command": "   "}, runner=calls.append)
    handlers.run_shell_command({}, runner=calls.append)
    assert calls == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/core/test_handlers.py -k run_shell_command -v`
Expected: FAIL — `AttributeError: ... has no attribute 'run_shell_command'`

- [ ] **Step 3: Implement**

In `src/mpk_deck/core/handlers.py`:

```python
def run_shell_command(params: dict, *, runner=None) -> None:
    """Fire-and-forget shell command on a pad/key press. No window, no output
    capture - same trust level as launch_program's arbitrary path."""
    command = (params.get("command") or "").strip()
    if not command:
        logger.info("run_shell_command: no command")
        return
    (runner or _default_command_runner)(command)


def _default_command_runner(command: str) -> None:
    subprocess.Popen(
        command,
        shell=True,
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
```

(`subprocess` is already imported at the top of the file.)

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/core/test_handlers.py -k run_shell_command -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Register in the engine**

In `src/mpk_deck/ui/main_window.py`, add `run_shell_command` to the handlers import block, and in `build_action_engine` with the other `register_trigger` calls:

```python
    engine.register_trigger("run_shell_command", run_shell_command)
```

- [ ] **Step 6: Run the full suite**

Run: `pytest`
Expected: 277 passed

- [ ] **Step 7: Commit**

```bash
git add src/mpk_deck/core/handlers.py src/mpk_deck/ui/main_window.py tests/core/test_handlers.py
git commit -m "feat(core): run_shell_command handler (fire-and-forget shell=True) + registration"
```

---

## Task 3: `media_key` handler

**Files:**
- Modify: `src/mpk_deck/core/handlers.py`
- Modify: `src/mpk_deck/ui/main_window.py`
- Test: `tests/core/test_handlers.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `handlers.media_key(params: dict, *, sender=None) -> None`
  - `handlers._default_media_key_sender(vk: int) -> None`
  - `handlers._MEDIA_VK: dict[str, int]` — keys `"play_pause"`, `"next"`, `"prev"`, `"stop"`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_handlers.py`:

```python
def test_media_key_sends_correct_virtual_key():
    calls = []
    handlers.media_key({"key": "play_pause"}, sender=calls.append)
    handlers.media_key({"key": "next"}, sender=calls.append)
    handlers.media_key({"key": "prev"}, sender=calls.append)
    handlers.media_key({"key": "stop"}, sender=calls.append)
    assert calls == [0xB3, 0xB0, 0xB1, 0xB2]


def test_media_key_unknown_or_missing_is_noop():
    calls = []
    handlers.media_key({"key": "volume_up"}, sender=calls.append)
    handlers.media_key({}, sender=calls.append)
    assert calls == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/core/test_handlers.py -k media_key -v`
Expected: FAIL — `AttributeError: ... has no attribute 'media_key'`

- [ ] **Step 3: Implement**

In `src/mpk_deck/core/handlers.py`:

```python
_MEDIA_VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2}


def media_key(params: dict, *, sender=None) -> None:
    """Send a media transport key to the OS. No-op-looking when nothing in the
    foreground consumes media keys - that is expected, not an error."""
    vk = _MEDIA_VK.get(params.get("key"))
    if vk is None:
        logger.info("media_key: unknown key %r", params.get("key"))
        return
    (sender or _default_media_key_sender)(vk)


def _default_media_key_sender(vk: int) -> None:
    import win32api
    import win32con

    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/core/test_handlers.py -k media_key -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Register in the engine**

In `src/mpk_deck/ui/main_window.py`, add `media_key` to the handlers import block, and in `build_action_engine`:

```python
    engine.register_trigger("media_key", media_key)
```

- [ ] **Step 6: Run the full suite**

Run: `pytest`
Expected: 279 passed

- [ ] **Step 7: Commit**

```bash
git add src/mpk_deck/core/handlers.py src/mpk_deck/ui/main_window.py tests/core/test_handlers.py
git commit -m "feat(core): media_key handler (play_pause/next/prev/stop) + registration"
```

---

## Task 4: config dialog — three new actions + combo page

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`
- Modify: `src/mpk_deck/ui/action_icons.py`
- Test: `tests/ui/test_action_config_dialog.py`

**Interfaces:**
- Consumes: `ACTION_TYPE` values from Tasks 1-3 (`set_display_brightness` continuous, `run_shell_command` + `media_key` trigger).
- Produces: the dialog offers `밝기` / `명령 실행` / `미디어 키`; `result_binding()` returns a `Binding` with `params={}` (brightness), `params={"command": str}` (shell), `params={"key": str}` (media_key).

- [ ] **Step 1: Write the failing tests**

Read `tests/ui/test_action_config_dialog.py` first to match its fixture style (offscreen `QApplication`, how it constructs `ActionConfigDialog`). Then add:

```python
def test_dialog_offers_the_three_new_actions(qapp):
    dlg = _make_dialog("knob_2")
    assert set(dlg._tiles) >= {"set_display_brightness", "run_shell_command", "media_key"}


def test_shell_command_round_trips_through_result_binding(qapp):
    dlg = _make_dialog("pad_1")
    dlg._select_action("run_shell_command")
    dlg._command_edit.setText("shutdown /h")
    b = dlg.result_binding()
    assert b.action == "run_shell_command"
    assert b.type == "trigger"
    assert b.params == {"command": "shutdown /h"}


def test_media_key_round_trips_and_reloads(qapp):
    dlg = _make_dialog("pad_1")
    dlg._select_action("media_key")
    idx = dlg._media_combo.findData("next")
    dlg._media_combo.setCurrentIndex(idx)
    b = dlg.result_binding()
    assert b.action == "media_key"
    assert b.params == {"key": "next"}

    dlg2 = _make_dialog("pad_1", binding=b)
    assert dlg2._media_combo.currentData() == "next"


def test_brightness_selects_its_page(qapp):
    dlg = _make_dialog("knob_2")
    dlg._select_action("set_display_brightness")
    assert dlg._param_stack.currentIndex() == dlg._page_for_action["set_display_brightness"]
```

Adjust `_make_dialog` / `qapp` to whatever the file already uses (it may inline these — reuse the existing pattern, don't invent a new fixture).

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/ui/test_action_config_dialog.py -k "new_actions or shell_command or media_key or brightness" -v`
Expected: FAIL — `KeyError`/`AttributeError` on `set_display_brightness` / `_command_edit` / `_media_combo`

- [ ] **Step 3: Add the table entries**

In `src/mpk_deck/ui/action_config_dialog.py`:

`ACTION_CHOICES` — append three entries (before `switch_bank` so "Add Bank" stays last):

```python
    ("set_display_brightness", "\U0001f506", "Display Brightness"),
    ("run_shell_command", "⌨", "Run Command"),
    ("media_key", "⏯", "Media Key"),
```

`ACTION_TYPE` — add:

```python
    "set_display_brightness": "continuous",
    "run_shell_command": "trigger",
    "media_key": "trigger",
```

`PARAM_KEY` — add:

```python
    "set_display_brightness": None,
    "run_shell_command": "command",
    "media_key": "key",
```

- [ ] **Step 4: Add the combo-page helper**

Add near `_add_note_page`:

```python
    def _add_combo_page(self, action: str, label_text: str, options: list[tuple[str, str]]) -> QComboBox:
        page, layout = self._page_shell(label_text)
        combo = QComboBox()
        for value, text in options:
            combo.addItem(text, value)
        layout.addWidget(combo)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return combo
```

- [ ] **Step 5: Build the three pages**

In `_build_param_stack`, after the existing `self._add_layout_page()` line, add:

```python
        self._add_note_page(
            "set_display_brightness", "디스플레이 밝기",
            "노브를 돌리면 내장 화면 밝기가 따라갑니다. 추가 설정 없음.",
        )
        self._command_edit = self._add_line_page(
            "run_shell_command", "실행할 명령", "예: shutdown /h",
            "누르면 명령을 실행합니다. 셸 기능(파이프, && 등) 사용 가능.",
        )
        self._media_combo = self._add_combo_page(
            "media_key", "미디어 키",
            [("play_pause", "재생/일시정지"), ("next", "다음 곡"), ("prev", "이전 곡"), ("stop", "정지")],
        )
```

Then extend `self._page_for_action` with the three new indices. The pages are added in order after `apply_layout` (index 6), so:

```python
            "set_display_brightness": 7,
            "run_shell_command": 8,
            "media_key": 9,
```

Verify by counting `self._param_stack.addWidget` calls — if the count differs, use the actual running index. (`apply_layout` = 6 today; the three new pages are 7, 8, 9.)

- [ ] **Step 6: Wire `_param_edit_for` and the load/result paths**

`_param_edit_for` — add the shell entry:

```python
            "run_shell_command": self._command_edit,
```

`result_binding()` — add a `media_key` branch before the generic `PARAM_KEY` block (mirroring the `apply_layout` branch):

```python
        if action == "media_key":
            return Binding(
                control=self._control, type="trigger", action="media_key",
                params={"key": self._media_combo.currentData() or "play_pause"},
                label=label, icon=icon,
            )
```

`_apply_binding()` — add a `media_key` branch before the generic `PARAM_KEY` block:

```python
        if binding.action == "media_key":
            i = self._media_combo.findData(binding.params.get("key", "play_pause"))
            if i >= 0:
                self._media_combo.setCurrentIndex(i)
            return
```

(`set_display_brightness` and `run_shell_command` need no special branch — brightness has no params, shell uses the generic `PARAM_KEY` line-edit path now that `_param_edit_for` knows `_command_edit`.)

- [ ] **Step 7: Add labels + icons in `action_icons.py`**

`ACTION_KO_LABEL` — add:

```python
    "set_display_brightness": "밝기",
    "run_shell_command": "명령 실행",
    "media_key": "미디어 키",
```

`_ACTION_SVG` — add a glyph for each of the three using the existing `{accent}` / `{neutral}` template convention (look at a neighbouring entry for the exact stroke/viewBox pattern):
- `set_display_brightness`: a sun — a filled `{accent}` centre circle + 8 short `{accent}` rays.
- `run_shell_command`: a `{neutral}` rounded-rect terminal frame with a `{accent}` `>` chevron and underscore.
- `media_key`: a `{accent}` right-triangle play glyph with two `{accent}` pause bars beside it.

`_ACTION_SVG_KNOB` — add a `set_display_brightness` entry (the knob-badge variant, same rule as `set_system_volume`'s knob entry).

- [ ] **Step 8: Run the dialog tests**

Run: `pytest tests/ui/test_action_config_dialog.py -v`
Expected: PASS (existing + 4 new)

- [ ] **Step 9: Run the full suite**

Run: `pytest`
Expected: 283 passed

- [ ] **Step 10: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py src/mpk_deck/ui/action_icons.py tests/ui/test_action_config_dialog.py
git commit -m "feat(ui): brightness / run-command / media-key actions in the config dialog"
```

---

## Task 5: natural-language coverage

**Files:**
- Modify: `src/mpk_deck/core/nl_action.py`
- Test: `tests/core/test_nl_action.py`

**Interfaces:**
- Consumes: the three action names + types from Tasks 1-3.
- Produces: `parse_nl_action` can return a `Binding` for `set_display_brightness` (`params={}`), `run_shell_command` (`params={"command": str}`), `media_key` (`params={"key": str}`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_nl_action.py` (reuse `FakeClient` / `_tool_use_response` from the top of the file):

```python
def test_nl_proposes_display_brightness():
    client = FakeClient(_tool_use_response({"action": "set_display_brightness"}))
    result = parse_nl_action("화면 밝기 조절", PROGRAMS, client=client)
    assert result.action == "set_display_brightness"
    assert result.type == "continuous"
    assert result.params == {}


def test_nl_proposes_shell_command():
    client = FakeClient(_tool_use_response({"action": "run_shell_command", "command": "shutdown /s /t 0"}))
    result = parse_nl_action("컴퓨터 종료 명령", PROGRAMS, client=client)
    assert result.action == "run_shell_command"
    assert result.type == "trigger"
    assert result.params == {"command": "shutdown /s /t 0"}


def test_nl_shell_command_empty_is_rejected():
    client = FakeClient(_tool_use_response({"action": "run_shell_command", "command": "   "}))
    assert parse_nl_action("빈 명령", PROGRAMS, client=client) is None


def test_nl_proposes_media_key():
    client = FakeClient(_tool_use_response({"action": "media_key", "media_key": "next"}))
    result = parse_nl_action("다음 곡", PROGRAMS, client=client)
    assert result.action == "media_key"
    assert result.params == {"key": "next"}


def test_nl_media_key_bad_value_is_rejected():
    client = FakeClient(_tool_use_response({"action": "media_key", "media_key": "rewind"}))
    assert parse_nl_action("되감기", PROGRAMS, client=client) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/core/test_nl_action.py -k "brightness or shell or media" -v`
Expected: FAIL — `_to_binding` returns `None` for the unknown actions (so `result` is `None`, `AttributeError` on `.action`)

- [ ] **Step 3: Implement**

In `src/mpk_deck/core/nl_action.py`:

`ACTION_TYPE` — add:

```python
    "set_display_brightness": "continuous",
    "run_shell_command": "trigger",
    "media_key": "trigger",
```

`_TOOL["input_schema"]["properties"]` — add:

```python
            "command": {
                "type": "string",
                "description": "Required for run_shell_command; a shell command line (run with shell=True).",
            },
            "media_key": {
                "type": "string",
                "enum": ["play_pause", "next", "prev", "stop"],
                "description": "Required for media_key; which media transport key to send.",
            },
```

`_TOOL["description"]` — append one sentence: ` "run_shell_command's command is run in a shell; media_key is one of play_pause/next/prev/stop."`

`_to_binding` — add branches before the final `else`:

```python
    elif action == "set_display_brightness":
        params = {}
    elif action == "run_shell_command":
        command = (data.get("command") or "").strip()
        if not command:
            return None
        params = {"command": command}
    elif action == "media_key":
        key = data.get("media_key")
        if key not in ("play_pause", "next", "prev", "stop"):
            return None
        params = {"key": key}
```

The current final `else:  # set_system_volume` stays as the fallthrough for `set_system_volume` and `apply_layout` is already handled above — verify the branch order still ends with `set_system_volume` reachable.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/core/test_nl_action.py -v`
Expected: PASS (existing + 5 new)

- [ ] **Step 5: Run the full suite**

Run: `pytest`
Expected: 288 passed

- [ ] **Step 6: Commit**

```bash
git add src/mpk_deck/core/nl_action.py tests/core/test_nl_action.py
git commit -m "feat(core): NL coverage for brightness / shell command / media key"
```

---

## Task 6: docs + final verification

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Update `CONTEXT.md`**

In the `core/handlers.py` bullet, extend the handler list with `set_display_brightness` (continuous, WMI built-in panel, ~10 Hz throttle), `run_shell_command` (trigger, `shell=True` fire-and-forget), `media_key` (trigger, `keybd_event` VK_MEDIA_*). Add to the "현재 진행 상태" / D section that D-rest (brightness / shell / media keys + NL) is built and committed, **not hardware-verified**, and list the live-only checks: actual panel brightness change, media keys landing on a real player, the NL dialog proposing all three with a real API key. Note the shared risk: brightness uses `win32com` COM on the continuous-dispatch path, same as the still-open volume-knob bug.

- [ ] **Step 2: Full suite + lint sanity**

Run: `pytest`
Expected: 288 passed

Run: `python -c "import mpk_deck.core.handlers; import mpk_deck.core.nl_action; import mpk_deck.ui.action_config_dialog"`
Expected: no error (module import guard for the lazy Windows deps holds)

- [ ] **Step 3: Commit**

```bash
git add CONTEXT.md
git commit -m "docs(mpk-deck): record D-rest action types (brightness/shell/media keys)"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| §1.1 brightness on a knob, throttled | Task 1 |
| §1.2 shell command fire-and-forget | Task 2 |
| §1.3 media key with dropdown | Task 3 (handler) + Task 4 (dropdown) |
| §2.1 `set_display_brightness` signature + WMI adapter + throttle | Task 1 |
| §2.2 `run_shell_command` signature + `shell=True` adapter | Task 2 |
| §2.3 `media_key` signature + `_MEDIA_VK` + `keybd_event` adapter | Task 3 |
| §3.2 engine registration | Tasks 1-3 Step 5 |
| §3.3 dialog tables + combo page + result/load | Task 4 |
| §3.4 KO labels + SVG glyphs | Task 4 Step 7 |
| §3.5 NL `ACTION_TYPE` + tool schema + `_to_binding` | Task 5 |
| §6 tests (handlers, nl_action, dialog) | Tasks 1-5 |
| §8 `CONTEXT.md` | Task 6 |

No gaps. Volume-knob bug is explicitly out of scope (spec §1 / §7 risk 1) — no task, by design.

**2. Placeholder scan** — every code step has literal code. Task 4 Step 7 (SVG glyphs) describes three icons by shape rather than pasting final SVG path data; this is deliberate — the exact path syntax must match the neighbouring `_ACTION_SVG` entries' viewBox/stroke conventions, which the implementer reads in-file. The shapes and colour slots (`{accent}`/`{neutral}`) are specified.

**3. Type consistency** — `set_display_brightness(params, value, *, brightness_setter, now)`, `run_shell_command(params, *, runner)`, `media_key(params, *, sender)`, `_should_apply_now(key, min_interval_s, now)`, `_MEDIA_VK` keys `play_pause/next/prev/stop`, dialog `_media_combo` / `_command_edit`, NL param key `"command"` / `"key"` — consistent across Tasks 1-6 and match the spec.
