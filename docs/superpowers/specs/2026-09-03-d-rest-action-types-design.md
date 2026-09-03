# D-rest — action type expansion (brightness / shell / media keys) — design

**Date:** 2026-09-03
**Repo:** mpk-deck
**Status:** implemented on branch `d-rest-action-types` (Codex), independently
reviewed (Claude/Opus). Not hardware-verified.

**Post-review adjustments (2026-09-03):** `_BRIGHTNESS_MIN_INTERVAL_S` shipped
at **0.3 s** (~3 Hz), not the 0.1 s / "10 Hz" written below — at 0.1 s the
window is ~one WMI call's cost, so it did not bound GUI-thread occupancy.
Parked (not fixed on this branch): (a) the dropped final knob value is
proportional to turn speed — proper fix is a latest-value-wins worker
thread, entangled with the open volume-knob COM investigation; (b) a
continuous action can still be bound to a pad/key and silently no-op
(pre-existing for volume/scroll — a control-kind filter on the tile picker +
NL is a follow-up task).
**Round:** sub-project **D-rest** — the part of "action type expansion" left
after the window remember/restore part was split out as Workspace Layouts
(2026-09-02). Adds the three remaining action types the D item named plus
natural-language coverage for them.

**Size note:** one implementation plan. All three action types follow the
existing "add an action" recipe (`mpk-deck/CLAUDE.md`): handler + adapter in
`core/handlers.py`, register in `build_action_engine`, three tables +
param page in `ui/action_config_dialog.py`, KO label + SVG in
`ui/action_icons.py`, and `core/nl_action.py` (`ACTION_TYPE` + tool schema +
`_to_binding`). Pure-function / seam-injection tests only — no new Qt-widget
test surface beyond the config-dialog page checks already covered.

---

## 1. Goal & completion criteria

Three new things a control can be bound to:

1. **Display brightness** on a knob — turning the knob sets the built-in
   laptop panel's brightness.
2. **Run a shell command** on a pad/key press.
3. **Media transport key** (play/pause, next, prev, stop) on a pad/key press.

Done when:

1. The config dialog's action picker offers **밝기**, **명령 실행**, and
   **미디어 키** alongside the existing eight.
   - 밝기: no parameters (a note page, like System Volume).
   - 명령 실행: a single-line text field for the command.
   - 미디어 키: a dropdown with the four keys.
2. A knob bound to 밝기 changes the panel brightness as it turns, throttled so
   the UI/MIDI never stall (see §4).
3. A pad bound to 명령 실행 runs its command fire-and-forget on press (no
   window, no output capture), the same trust level as Launch Program.
4. A pad bound to 미디어 키 sends the selected media key to the OS on press.
5. All three round-trip through `config/actions.yaml` (`load_config` /
   `save_config`) unchanged — no schema change, just new `action` values.
6. `core/nl_action.py` can propose all three from plain language
   ("화면 밝게", "메모장 켜는 명령 실행", "다음 곡"). As today, an NL
   proposal only fills the dialog fields — the user still presses Save.
7. `pytest` green; new pure-function / seam tests cover each adapter, the
   throttle, and each NL branch.

**Explicitly out of scope:** external-monitor brightness (DDC/CI, needs a new
dependency — deferred), volume mute/up/down media keys (volume is the knob's
job), any `config/actions.yaml` migration, and the volume-knob bug (tracked
separately — see §7 risk 1).

---

## 2. Action types

All adapters lazy-import their Windows dependency inside the function so the
module still imports on non-Windows (existing rule, `mpk-deck/CLAUDE.md`).
Every adapter is an injectable seam (`brightness_setter=` / `runner=` /
`sender=`), matching `set_system_volume`'s `volume_setter=` and
`scroll_*`'s `sender=`.

### 2.1 `set_display_brightness` — continuous

```
set_display_brightness(params: dict, value: float, *, brightness_setter=None, now=None) -> None
```

- `value` is 0.0–1.0 (already normalized by `translate()` for a knob CC).
  Clamp to `[0.0, 1.0]`, convert to an integer percent `round(value * 100)`.
- Throttled: apply at most once per `_BRIGHTNESS_MIN_INTERVAL_S` (0.1 s → ~10
  Hz). Between applies, drop intermediate values (the knob's next event
  carries the newer absolute value anyway — no missed final position because
  the knob keeps sending while turning; a `ponytail:` comment notes that a
  knob left exactly between throttle windows lands one tick stale, which is
  imperceptible for brightness).
- `_default_brightness_setter(percent: int)`:
  ```python
  import win32com.client
  wmi = win32com.client.GetObject(r"winmgmts:\\.\root\WMI")
  for m in wmi.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods"):
      m.WmiSetBrightness(1, percent)  # (timeout_seconds, brightness_percent)
  ```
  Verified available on the dev machine 2026-09-03 (`WmiMonitorBrightness`
  read + `WmiMonitorBrightnessMethods` present, no admin needed).
- `params` is `{}`.
- Registered with `engine.register_continuous`.

### 2.2 `run_shell_command` — trigger

```
run_shell_command(params: dict, *, runner=None) -> None
```

- `params["command"]` — a shell command string. Empty/missing → log at info
  and return (no-op).
- `_default_command_runner(command: str)`:
  ```python
  import subprocess
  subprocess.Popen(
      command, shell=True, close_fds=True,
      creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
  )
  ```
  Fire-and-forget: no `wait`, no `PIPE`, no output handling. `shell=True` is
  deliberate — the user wants shell features (`&&`, pipes, `%VAR%`).
- Trust model: `config/actions.yaml` is the user's own file that they edit by
  hand or through the dialog; running an arbitrary command from it is the same
  exposure as `launch_program`'s arbitrary `path`. An NL proposal never runs —
  it only populates the dialog field, and the user presses Save.
- Registered with `engine.register_trigger`.

### 2.3 `media_key` — trigger

```
media_key(params: dict, *, sender=None) -> None
```

- `params["key"]` ∈ `{"play_pause", "next", "prev", "stop"}`. Unknown/missing
  → log at info and return.
- VK map (module constant):
  ```python
  _MEDIA_VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2}
  ```
- `_default_media_key_sender(vk: int)`:
  ```python
  import win32api, win32con
  win32api.keybd_event(vk, 0, 0, 0)
  win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
  ```
- One action with a `key` parameter, not four separate picker tiles (the
  picker grid goes 8 → 11 tiles as it is; 12 would be four extra rows of
  clutter for one concept).
- No-op-looking behaviour when nothing in the foreground consumes media keys
  is expected, not a bug — documented in `CONTEXT.md`.
- Registered with `engine.register_trigger`.

---

## 3. Wiring — the "add an action" recipe

### 3.1 `core/handlers.py`
Add the three handlers + three `_default_*` adapters + the brightness
throttle helper:

```python
_LAST_APPLIED: dict[str, float] = {}   # ponytail: module dict, fine for a handful of throttled controls

def _should_apply_now(key: str, min_interval_s: float, now: float) -> bool:
    last = _LAST_APPLIED.get(key)
    if last is not None and now - last < min_interval_s:
        return False
    _LAST_APPLIED[key] = now
    return True
```

`set_display_brightness` calls `_should_apply_now("brightness", 0.1, now or time.monotonic())`.

### 3.2 `ui/main_window.py` — `build_action_engine`
```python
engine.register_continuous("set_display_brightness", set_display_brightness)
engine.register_trigger("run_shell_command", run_shell_command)
engine.register_trigger("media_key", media_key)
```
Plus the three names in the `from mpk_deck.core.handlers import (...)` list.

### 3.3 `ui/action_config_dialog.py`
- `ACTION_CHOICES` += `("set_display_brightness", "🔆", "Display Brightness")`,
  `("run_shell_command", "⌨", "Run Command")`,
  `("media_key", "⏯", "Media Key")`.
- `ACTION_TYPE` += `set_display_brightness: "continuous"`,
  `run_shell_command: "trigger"`, `media_key: "trigger"`.
- `PARAM_KEY` += `set_display_brightness: None`,
  `run_shell_command: "command"`, `media_key: "key"`.
- Param pages:
  - `set_display_brightness` → `_add_note_page("set_display_brightness",
    "디스플레이 밝기", "노브를 돌리면 내장 화면 밝기가 따라갑니다. 추가 설정 없음.")`
  - `run_shell_command` → `_add_line_page("run_shell_command", "실행할 명령",
    "예: shutdown /h", "누르면 명령을 실행합니다. 셸 기능(파이프, &&) 사용 가능.")`
  - `media_key` → **new `_add_combo_page(action, heading, options: list[tuple[value, label]])`**
    holding a `QComboBox`; store the combo on `self._media_key_combo`.
- `_page_for_action` += the three new page indices.
- `result_binding()` — for `media_key`, read `self._media_key_combo.currentData()`
  into `params["key"]` (same shape as how the layout page reads its selection);
  `run_shell_command` uses the generic `PARAM_KEY` line-edit path;
  `set_display_brightness` has no params.
- When an existing binding is loaded for edit, select the combo entry matching
  `binding.params.get("key")`.

### 3.4 `ui/action_icons.py`
- `ACTION_KO_LABEL` += `set_display_brightness: "밝기"`,
  `run_shell_command: "명령 실행"`, `media_key: "미디어 키"`.
- `_ACTION_SVG` (and `_ACTION_SVG_KNOB` for brightness) += a glyph each,
  using the existing `{accent}` / `{neutral}` template slots: a sun/rays for
  brightness, a `>_` terminal for command, a play/pause for media key.

### 3.5 `core/nl_action.py`
- `ACTION_TYPE` += the three (same values as the dialog's).
- `_TOOL["input_schema"]["properties"]` += 
  - `command`: `{"type": "string", "description": "Required for run_shell_command; a shell command line."}`
  - `media_key`: `{"type": "string", "enum": ["play_pause", "next", "prev", "stop"], "description": "Required for media_key."}`
- `_TOOL["description"]` — one sentence that `command` is run in a shell and
  `media_key` is one of the four transport keys.
- `_to_binding` branches:
  - `set_display_brightness` → `params = {}`
  - `run_shell_command` → `command = (data.get("command") or "").strip()`;
    empty → `return None`; `params = {"command": command}`
  - `media_key` → `key = data.get("media_key")`; not in the four-set →
    `return None`; `params = {"key": key}`

---

## 4. Performance / threading

- **Brightness throttle** (§3.1): WMI `WmiSetBrightness` costs ~50–100 ms per
  call and a knob emits tens of CC/s. Without the throttle a fast turn queues
  dozens of ~80 ms calls and the thread they run on stalls. 10 Hz + drop
  intermediates keeps it smooth; brightness is coarse enough that a dropped
  intermediate value is invisible.
- **Thread**: continuous engine calls are already marshalled to the GUI
  thread by `MPKController`'s `dispatch` seam
  (`QTimer.singleShot(0, self, fn)` in `MainWindow`). `set_display_brightness`
  rides that path — it does not add its own threading. See §7 risk 1.
- `run_shell_command` / `media_key` are trigger actions — one cheap call per
  press, no throttle needed. `Popen` returns immediately (detached).

---

## 5. Error handling

- Every adapter's failure is already contained: `ActionEngine.trigger` and
  `set_continuous` wrap the handler in `try/except` and log a warning
  (`"... handler for X failed"`) without crashing. New handlers add no new
  swallowing.
- Empty command / unknown media key / missing brightness method: log at
  info, no-op — never raise.
- WMI query returning zero instances (e.g. a desktop with no
  DDC-less panel): the `for` loop simply does nothing; log at info once.

---

## 6. Testing

Pure-function / seam-injection `pytest`, mirroring the repo's structure.

**`tests/core/test_handlers.py`**
- `set_display_brightness`: seam receives `round(value*100)` for value 0.0,
  0.5, 1.0; out-of-range value is clamped; with `now` injected, two calls
  inside 0.1 s → seam called once, a call after 0.1 s → called again.
- `run_shell_command`: runner seam receives the exact command string; empty
  / missing `command` → runner not called.
- `media_key`: sender seam receives `0xB3` for `play_pause` etc.; unknown key
  → sender not called.

**`tests/core/test_nl_action.py`**
- Mock client returns a `set_display_brightness` tool input → Binding with
  `type="continuous"`, `params={}`.
- `run_shell_command` input with a command → Binding; empty command → `None`.
- `media_key` input with `next` → Binding `params={"key": "next"}`; a bogus
  key → `None`.

**`tests/ui/test_action_config_dialog.py`**
- Selecting each new action shows the mapped page.
- A `run_shell_command` binding and a `media_key` binding survive
  `result_binding()` → save → `load_config` round-trip.
- Loading an existing `media_key` binding pre-selects the right combo entry.

**Live-only (documented in `CONTEXT.md`, user's verification):** actual panel
brightness change; media keys landing on a real player; the NL dialog with a
real `ANTHROPIC_API_KEY` proposing all three.

---

## 7. Risks

1. **Brightness shares the volume knob's COM path.** `WmiSetBrightness` via
   `win32com` does COM work on whatever thread the continuous handler runs
   on — the same class of issue as the still-open volume-knob bug. Brightness
   rides on whatever fix that bug gets (it is a `dispatch`-seam / COM-apartment
   / endpoint-caching question, pending a real traceback from the user). If
   D-rest ships before the volume bug is resolved, brightness will likely hit
   the same wall on hardware. **Recommendation: get the volume traceback and
   fix that first**, or accept brightness lands with a known-shared defect that
   the volume fix also clears. Not a blocker for writing/merging the code with
   passing seam tests.
2. **WMI brightness is slow and some panels rate-limit.** Mitigated by the
   10 Hz throttle; if a panel still lags, the interval is one constant to
   tune.
3. **`media_key` is a no-op when nothing consumes media keys.** Expected OS
   behaviour, documented, not a bug.
4. **`shell=True` runs arbitrary commands** from `config/actions.yaml`.
   Accepted: same trust boundary as `launch_program`'s path; NL proposes but
   never auto-runs.

---

## 8. Files touched

| File | Change |
|---|---|
| `src/mpk_deck/core/handlers.py` | 3 handlers + 3 adapters + `_should_apply_now` throttle helper + `_MEDIA_VK` |
| `src/mpk_deck/ui/main_window.py` | 3 `register_*` calls + import names |
| `src/mpk_deck/ui/action_config_dialog.py` | `ACTION_CHOICES` / `ACTION_TYPE` / `PARAM_KEY` +3, `_add_combo_page` helper, `_page_for_action` +3, `result_binding()` combo read, edit-load combo preselect |
| `src/mpk_deck/ui/action_icons.py` | `ACTION_KO_LABEL` +3, `_ACTION_SVG` (+`_ACTION_SVG_KNOB`) +3 glyphs |
| `src/mpk_deck/core/nl_action.py` | `ACTION_TYPE` +3, tool schema `command` + `media_key`, `_to_binding` 3 branches |
| `tests/core/test_handlers.py` | new adapter + throttle tests |
| `tests/core/test_nl_action.py` | new NL branch tests |
| `tests/ui/test_action_config_dialog.py` | new page-switch + round-trip tests |
| `CONTEXT.md` | add the three action types to the handlers list + the media-key / brightness live-verification notes |

`config/actions.yaml` is **not** a feature file — the current uncommitted
edits to it are manual test tinkering and get reverted separately.
