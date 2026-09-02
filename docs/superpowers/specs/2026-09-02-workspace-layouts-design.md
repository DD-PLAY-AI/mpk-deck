# Workspace Layouts — design

**Date:** 2026-09-02
**Repo:** mpk-deck
**Status:** approved for implementation (Codex-implemented; Claude wrote this spec)
**Round:** sub-project D, split out from "action type expansion" because it is
its own feature (ROADMAP calls it *Workspace Profiles*, Phase 2 — but it does
not depend on the mini monitor, so it is being done now).

**Size note:** likely two implementation plans — (1) `core/` (layout_store,
window_layout, browser_url, handler, nl_action) with pure/seam tests;
(2) `ui/` (dialog action + param page + `LayoutCaptureDialog` + view label
threading). Plan 1 can land and be tested before Plan 2 starts.

---

## 1. Goal & completion criteria

One pad restores a whole working environment: the saved programs and browser
sites open, each moved to its saved position and size.

Done when:

1. In the config dialog, choosing the new **레이아웃 (layout)** action lets the
   user either pick an existing saved layout or **save a new one**.
2. "Save new" shows a checklist of the windows currently open (title + which
   program). The user ticks the ones to include. Each ticked window's program
   path (or browser + URL) and geometry are captured.
3. Triggering a pad bound to that layout:
   - for each item already open (one matching window): moves/resizes that
     window to the saved geometry — **never launches a duplicate**;
   - for each item not open: launches the program (or opens the URL in the
     saved browser), waits for its window, then moves/resizes it.
4. Layout data persists in `%APPDATA%\mpk-deck\layouts.yaml` and survives an
   app restart (and a future packaged `.exe` — it is not stored next to the
   source).
5. The natural-language action config (`core/nl_action.py`) can also produce a
   layout binding (referencing an existing layout by name).
6. Restore runs off the GUI thread — the deck UI and MIDI never freeze while a
   layout is opening.

---

## 2. Non-goals (this round)

- Firefox URL capture (UIA tree differs). Firefox windows can still be captured
  as "a Firefox window at this geometry" with a manually-typed URL.
- A companion browser extension / CDP. UIA best-effort + manual fallback only.
- Capturing *all* tabs of a browser window — only the **active tab's** URL.
- Cross-DPI / cross-machine layout portability (geometry is physical pixels).
- Migrating `config/actions.yaml` into `%APPDATA%` — noted in §10, separate task.
- Virtual desktops, window z-order, "always on top", per-monitor DPI awareness
  changes.
- Editing individual item geometry by typing numbers. v1 capture is
  "arrange your windows, then save". Re-save to update.

---

## 3. Assumptions

- Windows only (matches the rest of the app).
- `pywin32` is available (dependency). `comtypes` is available transitively via
  `pycaw` — use it for UIA rather than adding `uiautomation`, unless comtypes
  proves impractical (then `uiautomation` may be added as a dependency).
- The user runs mpk-deck and the target programs at the same integrity level
  (no UAC elevation mismatch). If a target window is owned by an elevated
  process, positioning it may fail silently — log and continue.
- Chrome / Edge are Chromium and expose the address bar the same way in UIA.

---

## 4. Simpler alternatives considered

- **Store the layout inline in the binding's `params`** (like sensitivity).
  Rejected: layout blobs are large, several pads may want to share one layout,
  and a layout is conceptually a named thing, not a binding detail.
- **"Remember" pad + "Restore" pad, single window.** Rejected by the user —
  they want a multi-program scene captured from a checklist.
- **Deterministic layout only** (type a title + target x/y/w/h in the dialog,
  no capture step). Rejected — the user wants "arrange then save".
- **CDP / browser extension for exact URLs.** Deferred — needs setup (debug
  flag or extension install) that UIA does not.

---

## 5. Data model

### 5.1 `layouts.yaml`

Location: `user_data_dir() / "layouts.yaml"` where `user_data_dir()` is
`Path(os.environ["APPDATA"]) / "mpk-deck"` (created on first save). A new
`config.user_data_dir()` helper returns it; `config.LAYOUTS_PATH` is the file.

```yaml
layouts:
  coding_setup:
    name: "코딩 셋업"
    items:
      - kind: program
        path: "C:/Users/x/AppData/Local/Programs/Microsoft VS Code/Code.exe"
        title_match: "Visual Studio Code"   # substring, case-insensitive
        rect: [80, 60, 1280, 900]           # x, y, width, height (physical px, virtual-screen coords)
        maximized: false
      - kind: url
        url: "https://claude.ai/code"
        browser: chrome                     # chrome | edge | default
        title_match: "Claude"
        rect: [1400, 60, 520, 900]
        maximized: false
      - kind: program
        path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
        title_match: ""
        rect: [0, 0, 0, 0]
        maximized: true
```

Rules:
- `kind: program` → `path` required, `url`/`browser` absent.
- `kind: url` → `url` + `browser` required, `path` absent.
- `rect` is always present; ignored when `maximized: true` except as the
  "restore-down" rectangle passed to `SetWindowPlacement`.
- `title_match` is a best-effort disambiguator for matching an already-open
  window; empty string means "match on program/browser only".
- Unknown keys are ignored on load. A malformed item is logged and skipped
  (same policy as `action_registry._parse_binding`).

### 5.2 New module `core/layout_store.py`

```python
@dataclass
class LayoutItem:
    kind: Literal["program", "url"]
    rect: tuple[int, int, int, int]
    maximized: bool = False
    path: str = ""
    url: str = ""
    browser: str = ""          # "chrome" | "edge" | "default"
    title_match: str = ""

@dataclass
class Layout:
    name: str
    items: list[LayoutItem]

def load_layouts(path: str | Path | None = None) -> dict[str, Layout]:
    # never raises: missing file / bad YAML / bad structure -> {}
    # malformed individual layouts/items -> logged + skipped

def save_layouts(layouts: dict[str, Layout], path: str | Path | None = None) -> None:
    # atomic write (temp + os.replace), allow_unicode=True, mkdir parents
    # -- reuse the pattern from action_registry.save_config

def generate_layout_id(name: str, existing_ids: Iterable[str]) -> str:
    # slugify + dedupe -- copy action_registry.generate_bank_id
```

### 5.3 `Binding` integration

- New action `apply_layout`, type `trigger`, `params: {"layout_id": "<id>"}`.
- `ui/action_config_dialog.py`:
  - add `("apply_layout", <icon>, "Layout")` to `ACTION_CHOICES`
  - `ACTION_TYPE["apply_layout"] = "trigger"`, `PARAM_KEY["apply_layout"] = None`
  - `ACTION_KO_LABEL["apply_layout"] = "레이아웃"` in `ui/action_icons.py`
  - param page (§8.3)
- `ui/action_icons.py`: add an `_ACTION_SVG["apply_layout"]` + `_ACTION_SVG_KNOB`
  entry — a small grid of rectangles (a "scene"). `action_label` for
  `apply_layout` returns the layout's `name` when resolvable (pass a
  `layouts: dict[str, Layout]` through `update_bindings` the way `bank_names`
  is threaded), else "레이아웃".
- `MainWindow` loads layouts on startup, passes them to
  `MiniView`/`ExpandedView.update_bindings`, and reloads after a save.

---

## 6. Window enumeration & capture — `core/window_layout.py`

### 6.1 `list_open_windows(*, resolver=None) -> list[OpenWindow]`

```python
@dataclass(frozen=True)
class OpenWindow:
    hwnd: int
    title: str
    exe_path: str          # "" if it couldn't be resolved
    rect: tuple[int, int, int, int]
    maximized: bool
```

- `win32gui.EnumWindows`; keep a window when **all** hold:
  - `win32gui.IsWindowVisible(hwnd)`
  - `win32gui.GetWindowText(hwnd)` is non-empty
  - not a tool window: `GetWindowLong(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW == 0`
  - not DWM-cloaked: `DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED)` returns 0
    (filters UWP ghost windows) — wrap in try/except, treat failure as "not cloaked"
  - has a non-zero client rect
- `exe_path`: `GetWindowThreadProcessId` → open the process with
  `PROCESS_QUERY_LIMITED_INFORMATION` → `QueryFullProcessImageNameW`
  (via `ctypes`/`win32process`). On failure, `""`.
- `rect`: `GetWindowRect`. `maximized`: `GetWindowPlacement(hwnd)[1] == SW_SHOWMAXIMIZED`.
- `resolver` seam: optional `Callable[[], list[OpenWindow]]` for tests to inject
  a fake list.
- Exclude mpk-deck's own window (match by `exe_path` == current process, or by
  the known window title).

### 6.2 `capture_item(window: OpenWindow, *, url_reader=None) -> LayoutItem`

- `browser = browser_kind(window.exe_path)` (§7).
- If `browser` is not None → try `url = (url_reader or browser_url.active_tab_url)(window.hwnd)`.
  - success → `LayoutItem(kind="url", url=url, browser=browser, rect=..., maximized=..., title_match=<short title>)`
  - failure → still make a `url` item with `url=""` so the dialog can prompt;
    OR a `program` item pointing at the browser exe. **Decision: emit a `url`
    item with `url=""`** and let the capture dialog require the user to fill it
    (or drop that row).
- else → `LayoutItem(kind="program", path=window.exe_path, rect=..., maximized=..., title_match=<title>)`.
- `title_match`: for programs, a stable fragment of the title (e.g. for
  `"foo.py - Visual Studio Code"` store `"Visual Studio Code"` — take the
  segment after the last `" - "`, capped at ~40 chars). For urls, the page
  title fragment. Best-effort; empty is fine.

---

## 7. Browser detection & URL read — `core/browser_url.py`

### 7.1 `browser_kind(exe_path: str) -> str | None`

Basename match (case-insensitive): `chrome.exe` → `"chrome"`,
`msedge.exe` → `"edge"`, `firefox.exe` → `"firefox"`, else `None`.

### 7.2 `active_tab_url(hwnd: int) -> str | None`

Best-effort UIA read of the address bar of the window's **active tab**.

- Use `comtypes.client.GetModule("UIAutomationCore.dll")` +
  `CUIAutomation` → `IUIAutomation`.
- `automation.ElementFromHandle(hwnd)` → the browser window element.
- Find the address bar: a descendant with `ControlType == Edit` whose
  `Name`/`AutomationId` looks like an address bar. Chrome/Edge:
  `AutomationId == "view_1020"` is unreliable across versions — prefer a
  `TreeWalker` / `FindAll` for `ControlType.Edit` inside the toolbar
  (`ControlType.ToolBar`), take the one whose `Name` contains "주소"/"Address"
  /"URL"/"검색", falling back to the first `Edit` in the toolbar.
- Read `ValuePattern.CurrentValue` (or `LegacyIAccessiblePattern` value).
- Normalise: if it has no scheme and looks like a host, prepend `https://`.
  If it is empty or looks like a search term (has spaces, no dot), return `None`.
- Wrap the whole thing in try/except → `None` on any COM error.
- Must run on a thread where COM is initialised STA. The capture dialog runs
  on the GUI thread (Qt inits COM) — fine. If ever called from a worker,
  `CoInitialize()` first.
- Time-box: if the tree walk hasn't found the element in ~500 ms, give up.

Firefox: attempt the same generic "first Edit in a toolbar" walk; if it fails,
`None` (manual fallback).

---

## 8. Config dialog — capture & pick UI

### 8.1 Action entry

`apply_layout` is a normal rebindable action (not locked like `switch_bank`).
Its param page:

```
레이아웃
[ dropdown: <saved layout names>  ▼ ]        [ 새로 저장… ]   [ 편집… ]
현재 3개 항목 · 코딩 셋업
```

- dropdown lists `load_layouts()` by name; selecting one sets
  `params={"layout_id": <id>}`.
- **새로 저장…** opens the capture sub-dialog (§8.2). On accept it writes the
  new layout to `layouts.yaml`, refreshes the dropdown, and selects it.
- **편집…** re-opens the capture sub-dialog seeded with the selected layout's
  items shown as already-ticked *plus* the current open windows; accept
  overwrites that layout.
- If no layouts exist, the dropdown is empty and only **새로 저장…** is enabled;
  `result_binding()` for `apply_layout` with no selection returns
  `params={"layout_id": ""}` (a no-op handler — logs "no layout").

### 8.2 Capture sub-dialog `LayoutCaptureDialog`

Same glass styling as `ActionConfigDialog` (frameless, accent, theme-aware).

```
레이아웃 저장
이름 [ 코딩 셋업                    ]

포함할 창                                         [새로고침]
☑ Visual Studio Code            Code.exe          1280×900
☑ Claude - Chrome               chrome.exe  🌐    [URL: https://claude.ai/code   ]
☐ Spotify                       Spotify.exe       1000×700
☑ Chrome (전체화면)              chrome.exe  🌐    [URL:                          ]  ⚠ URL 필요
...
                                              [ 취소 ]   [ 저장 ]
```

- Populated from `list_open_windows()` → `capture_item()` per row.
- Browser rows show an editable URL field, pre-filled from the UIA read.
  A ticked browser row with an empty URL blocks **저장** (inline warning) —
  the user fills it or unticks the row.
- **저장** builds `Layout(name, items=[capture_item(...) for ticked rows])`,
  assigns an id via `generate_layout_id`, `save_layouts`.
- Non-blocking: `list_open_windows` + `capture_item` (incl. the UIA reads) run
  when the dialog opens; if that takes >~1 s show the list is loading. The UIA
  reads may be done lazily per browser row to keep the dialog snappy.

### 8.3 `nl_action.py`

Add `apply_layout` to `nl_action.ACTION_TYPE` and the tool schema with a
`layout_name` field. `_to_binding` resolves `layout_name` against
`load_layouts()` (exact, then case-insensitive) → `params={"layout_id": id}`;
no match → `None` (never invents a layout).

---

## 9. Restore — `core/window_layout.py` + handler

### 9.1 Handler `apply_layout(params, *, restore=None)` in `core/handlers.py`

```python
def apply_layout(params: dict, *, restore=None) -> None:
    layout_id = params.get("layout_id")
    if not layout_id:
        logger.info("apply_layout: no layout bound")
        return
    layout = load_layouts().get(layout_id)
    if layout is None:
        logger.warning("apply_layout: layout %s not found", layout_id)
        return
    (restore or _default_restore)(layout)
```

`_default_restore(layout)` spawns a **daemon `threading.Thread`** running
`restore_layout(layout)` and returns immediately. The engine dispatches
handlers on the GUI thread (batch A) — this handler must not block it.

### 9.2 `restore_layout(layout, *, window_lister=None, launcher=None, positioner=None, sleep=time.sleep)`

```
open_now = (window_lister or list_open_windows)()
for i, item in enumerate(layout.items):
    hwnd = _match(item, open_now)          # §9.3
    if hwnd is None:
        (launcher or _default_launch)(item)
        sleep(0.2 * i)                     # stagger launches a little
        hwnd = _poll_for_window(item, timeout=8.0, sleep=sleep)  # re-list every 0.25s
    if hwnd is not None:
        (positioner or position_window)(hwnd, item.rect, item.maximized)
        sleep(0.15)
        # browsers/Electron sometimes re-lay-out just after show -> position once more
        (positioner or position_window)(hwnd, item.rect, item.maximized)
    else:
        logger.warning("restore_layout: no window for %r", item)
```

### 9.3 `_match(item, open_windows) -> hwnd | None`  (C = option 1: reposition existing)

- `program`: windows whose `exe_path` basename == `Path(item.path).name`
  (case-insensitive). If `item.title_match`, prefer ones whose title contains
  it. Return the first; `None` if no candidates.
- `url`: windows whose `browser_kind(exe_path)` == `item.browser`
  (or any Chromium if `item.browser == "default"`). If `item.title_match`,
  require the title to contain it (so two Chrome windows are told apart);
  without a `title_match`, and with >1 candidate, return `None` so a new
  window is opened rather than hijacking an unrelated one.

### 9.4 `_default_launch(item)`

- `program`: `subprocess.Popen([item.path])` (list form, no shell). If the
  path is missing → log + skip.
- `url`:
  - resolve the browser exe: chrome/edge via `program_finder.list_installed_programs`
    match on basename, or a small hardcoded fallback of the usual install paths;
    `default` → `webbrowser.open(url)`.
  - `subprocess.Popen([browser_exe, "--new-window", item.url])`.

### 9.5 `position_window(hwnd, rect, maximized)`

- Clamp `rect` to the nearest visible monitor work area
  (`EnumDisplayMonitors` / `MonitorFromRect` + `GetMonitorInfo`), so a layout
  saved with a second monitor still lands on-screen when that monitor is gone.
  Keep width/height if they fit, else shrink to the work area.
- `maximized`: `SetWindowPlacement` with `showCmd = SW_SHOWMAXIMIZED` and the
  clamped rect as `rcNormalPosition`.
- else: `SetWindowPlacement` with `SW_SHOWNORMAL` + the clamped rect
  (`SetWindowPlacement` restores a maximised/minimised window first, unlike
  `SetWindowPos`). Follow with `SetWindowPos(hwnd, None, x, y, w, h, SWP_NOZORDER|SWP_NOACTIVATE)`.
- All calls wrapped — a failure on one window logs and does not abort the loop.

---

## 10. Config location & migration

- `config.user_data_dir()` → `Path(os.environ.get("APPDATA", Path.home())) / "mpk-deck"`,
  `mkdir(parents=True, exist_ok=True)` on first write.
- `config.LAYOUTS_PATH = user_data_dir() / "layouts.yaml"`.
- `actions.yaml` stays at its current source-relative path **for now**. A
  follow-up task should move it (and `QSettings`) under `user_data_dir()` with a
  one-time migration, so a packaged `.exe` has a single writable data home.
  Flag this in `CONTEXT.md`.

---

## 11. Testing strategy

Pure / seam-injected (pytest):

- `layout_store`: load/save round-trip, `allow_unicode`, missing file → `{}`,
  bad YAML → `{}`, malformed item skipped, `generate_layout_id` dedupe, atomic
  write leaves the old file intact on failure (mirror the
  `action_registry` tests).
- `browser_url.browser_kind`: chrome/edge/firefox/other/`""`.
- `window_layout._match`: program-by-basename, title disambiguation, url
  multi-candidate → `None`, `default` browser matches any Chromium.
- `window_layout.restore_layout` with fake `window_lister` / `launcher` /
  `positioner` / `sleep`: item already open → positioner called, launcher not;
  item absent → launcher then poll then positioner; poll timeout → logged,
  loop continues; the double-position call.
- `position_window` rect-clamp math as a pure helper
  (`clamp_rect_to_monitors(rect, monitors) -> rect`).
- `action_registry` / dialog: `apply_layout` binding round-trips;
  `action_label` resolves the layout name; dialog param page builds and
  `result_binding` returns `{"layout_id": ...}`.
- `nl_action`: `layout_name` resolves via an injected client + fake layouts;
  unknown name → `None`.

Manual (documented in the PR / CONTEXT):

- `list_open_windows` returns real windows, excludes mpk-deck + tool windows.
- UIA `active_tab_url` on a live Chrome and Edge window.
- Full capture → save → trigger → windows open and land correctly, including:
  one program already open (repositioned, not duplicated), a URL not open
  (launched + positioned), a maximised item, an item whose monitor is gone.
- Restore does not freeze the deck / MIDI (worker thread).

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| UIA address-bar element moves between browser versions → URL read breaks | generic "first Edit in a toolbar" walk + always-editable URL field in capture; feature degrades to manual, never crashes |
| Restore races: window positioned before it's ready → wrong place | poll for the window, then position twice (immediately + after 150 ms) |
| Launching many apps at once → CPU spike, slow | small stagger between launches; restore is on a worker thread so the UI stays live |
| `SetWindowPlacement` on an elevated / protected window fails | per-window try/except, log, continue |
| Saved geometry off-screen (monitor removed / resolution change) | `clamp_rect_to_monitors` before positioning |
| `%APPDATA%` unset (rare) | fall back to `Path.home() / ".mpk-deck"` |
| Worker thread calling win32 from non-GUI thread | `EnumWindows` / `SetWindowPlacement` / `SetWindowPos` are not thread-affine for other-process windows; safe. UIA is only called from the GUI-thread dialog. |
| Two windows of the same program, user wanted a specific one | `title_match` disambiguation; documented limitation when titles are identical |

---

## 13. Out of scope / future

- Move `actions.yaml` + `QSettings` under `user_data_dir()` (own task).
- CDP / companion extension for exact multi-tab capture.
- Firefox URL capture.
- Per-item "launch only, don't reposition" / "reposition only, don't launch" flags.
- Editing item geometry numerically in the dialog.
- Layouts that also set the active MPK bank / theme (a "scene" beyond windows).
- Saving window z-order and focus.

---

## 14. File-by-file summary (for the implementation plan)

| File | Change |
|---|---|
| `src/mpk_deck/config.py` | `user_data_dir()`, `LAYOUTS_PATH` |
| `src/mpk_deck/core/layout_store.py` | **new** — `Layout`, `LayoutItem`, load/save/id |
| `src/mpk_deck/core/window_layout.py` | **new** — `list_open_windows`, `capture_item`, `restore_layout`, `_match`, `position_window`, `clamp_rect_to_monitors` |
| `src/mpk_deck/core/browser_url.py` | **new** — `browser_kind`, `active_tab_url` (UIA) |
| `src/mpk_deck/core/handlers.py` | `apply_layout` handler (spawns worker) |
| `src/mpk_deck/core/action_engine` registration | `MainWindow.build_action_engine` registers `apply_layout` as a trigger |
| `src/mpk_deck/core/nl_action.py` | `apply_layout` in schema + `_to_binding` |
| `src/mpk_deck/ui/action_icons.py` | `ACTION_KO_LABEL`, `_ACTION_SVG`, `_ACTION_SVG_KNOB`, `action_label` layout-name resolution |
| `src/mpk_deck/ui/action_config_dialog.py` | `apply_layout` in `ACTION_CHOICES`/`ACTION_TYPE`/`PARAM_KEY`; param page with dropdown + 새로 저장/편집 |
| `src/mpk_deck/ui/layout_capture_dialog.py` | **new** — `LayoutCaptureDialog` |
| `src/mpk_deck/ui/mini_view.py`, `ui/expanded_view.py` | thread `layouts` through `update_bindings` for the label |
| `src/mpk_deck/ui/main_window.py` | load layouts on start, pass to views, reload after save |
| `pyproject.toml` | none expected (comtypes via pycaw); add `uiautomation` only if comtypes is impractical |
| `tests/` | per §11 |
| `CONTEXT.md` | document layouts, `user_data_dir()`, the pending `actions.yaml` move |
