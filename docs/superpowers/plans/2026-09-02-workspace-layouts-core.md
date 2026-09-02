# Workspace Layouts — Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the non-UI half of Workspace Layouts — persist named layouts, enumerate/capture open windows, read browser URLs, and restore a layout (launch + position) off the GUI thread.

**Architecture:** New `core/layout_store.py` (dataclasses + atomic YAML in `%APPDATA%`), `core/window_layout.py` (win32 enumerate/capture/position + a fully seam-injected `restore_layout`), `core/browser_url.py` (pure browser detection + best-effort UIA address-bar read). A new `apply_layout` trigger handler spawns a daemon thread so restore never blocks Qt. `nl_action.py` learns the action.

**Tech Stack:** Python 3.13, pywin32 (`win32gui`/`win32process`/`win32con`/`win32api`), comtypes (already present via pycaw) for UI Automation, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-workspace-layouts-design.md`

## Global Constraints

- Windows only. Windows-specific imports (`win32*`, `comtypes`, UIA) are **lazy** — imported inside the function that needs them, never at module top — so the module imports on any OS and under pytest.
- No new pip dependency. Use `comtypes` for UIA. Only if comtypes proves impractical may `uiautomation>=2.0` be added to `pyproject.toml` `dependencies` (`; sys_platform == 'win32'`).
- Every function that touches the OS or a subprocess takes an injectable seam (`window_lister=`, `launcher=`, `positioner=`, `url_reader=`, `sleep=`, `resolver=`) defaulting to the real implementation — mirror the existing `handlers.focus_window(finder=...)` / `set_system_volume(volume_setter=...)` pattern.
- Loaders never raise: missing file / bad YAML / bad structure → empty result; a malformed individual record → `logger.warning` + skip. Mirror `core/action_registry.load_config`.
- Atomic writes: temp file in the same dir → `flush` → `os.fsync` → `os.replace`; clean up the temp on failure. Copy `core/action_registry.save_config` exactly, including `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)`.
- `restore_layout` and anything it calls must be safe to run on a non-GUI thread. UIA (`browser_url.active_tab_url`) is only ever called from the GUI-thread dialog, never from `restore_layout`.
- Tests: `cd C:\DC\DD\mpk-deck && python -m pytest -q`. Currently 222 passing. `tests/` mirrors `src/mpk_deck/`. Pure functions get real pytest coverage; win32/COM/thread-spawning code is covered via injected seams — do not open real windows or MIDI ports in tests.

---

### Task 1: `config.user_data_dir()` + `LAYOUTS_PATH`

**Files:**
- Modify: `src/mpk_deck/config.py`
- Test: `tests/test_config.py` (create if absent)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `config.user_data_dir() -> pathlib.Path` — `%APPDATA%\mpk-deck`, falling back to `~/.mpk-deck` when `APPDATA` is unset. Does **not** create the directory.
  - `config.LAYOUTS_PATH: pathlib.Path` — `user_data_dir() / "layouts.yaml"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
from pathlib import Path

from mpk_deck import config


def test_user_data_dir_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    assert config.user_data_dir() == Path(r"C:\Users\x\AppData\Roaming") / "mpk-deck"


def test_user_data_dir_falls_back_to_home_without_appdata(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    assert config.user_data_dir() == Path.home() / ".mpk-deck"


def test_layouts_path_is_under_user_data_dir(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    # LAYOUTS_PATH is resolved at import time; re-derive to compare shape
    assert config.LAYOUTS_PATH.name == "layouts.yaml"
    assert config.LAYOUTS_PATH.parent.name == "mpk-deck"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: module 'mpk_deck.config' has no attribute 'user_data_dir'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/config.py — add near the top, after the existing imports
import os


def user_data_dir() -> Path:
    """Writable per-user data home. %APPDATA%\\mpk-deck on Windows, ~/.mpk-deck
    otherwise. Not created here - writers mkdir(parents=True, exist_ok=True)."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".mpk-deck"
    return base / "mpk-deck" if appdata else base


LAYOUTS_PATH = user_data_dir() / "layouts.yaml"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/config.py tests/test_config.py
git commit -m "feat(config): add user_data_dir() + LAYOUTS_PATH"
```

---

### Task 2: `core/layout_store.py`

**Files:**
- Create: `src/mpk_deck/core/layout_store.py`
- Test: `tests/core/test_layout_store.py`

**Interfaces:**
- Consumes: `config.LAYOUTS_PATH` (Task 1).
- Produces:
  - `LayoutItem` frozen dataclass: `kind: Literal["program","url"]`, `rect: tuple[int,int,int,int]`, `maximized: bool = False`, `path: str = ""`, `url: str = ""`, `browser: str = ""`, `title_match: str = ""`.
  - `Layout` dataclass: `name: str`, `items: list[LayoutItem]`.
  - `load_layouts(path: str | Path | None = None) -> dict[str, Layout]` — never raises.
  - `save_layouts(layouts: dict[str, Layout], path: str | Path | None = None) -> None` — atomic, `allow_unicode`, mkdir parents.
  - `generate_layout_id(name: str, existing_ids: Iterable[str]) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_layout_store.py
from pathlib import Path

import pytest

from mpk_deck.core.layout_store import (
    Layout,
    LayoutItem,
    generate_layout_id,
    load_layouts,
    save_layouts,
)


def _sample() -> dict[str, Layout]:
    return {
        "coding": Layout(
            name="코딩 셋업",
            items=[
                LayoutItem(kind="program", path="C:/x/Code.exe", rect=(80, 60, 1280, 900),
                           title_match="Visual Studio Code"),
                LayoutItem(kind="url", url="https://claude.ai/code", browser="chrome",
                           rect=(1400, 60, 520, 900), title_match="Claude"),
                LayoutItem(kind="program", path="C:/x/chrome.exe", rect=(0, 0, 0, 0), maximized=True),
            ],
        )
    }


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    assert load_layouts(path) == _sample()


def test_save_writes_readable_korean(tmp_path):
    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    assert "코딩 셋업" in path.read_text(encoding="utf-8")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_layouts(tmp_path / "nope.yaml") == {}


def test_load_bad_yaml_returns_empty(tmp_path):
    path = tmp_path / "layouts.yaml"
    path.write_text("]: [: not yaml", encoding="utf-8")
    assert load_layouts(path) == {}


def test_load_skips_a_malformed_item_but_keeps_the_layout(tmp_path, caplog):
    path = tmp_path / "layouts.yaml"
    path.write_text(
        "layouts:\n"
        "  a:\n"
        "    name: A\n"
        "    items:\n"
        "      - kind: program\n"
        "        path: C:/x.exe\n"
        "        rect: [1, 2, 3, 4]\n"
        "      - kind: nonsense\n",
        encoding="utf-8",
    )
    layouts = load_layouts(path)
    assert list(layouts) == ["a"]
    assert len(layouts["a"].items) == 1


def test_save_failure_leaves_existing_file_intact(tmp_path, monkeypatch):
    import mpk_deck.core.layout_store as ls

    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    monkeypatch.setattr(ls.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        save_layouts({"x": Layout(name="x", items=[])}, path)
    assert load_layouts(path) == _sample()
    assert list(tmp_path.iterdir()) == [path]


def test_generate_layout_id_slugifies_and_dedupes():
    assert generate_layout_id("My Setup!", existing_ids=[]) == "my_setup"
    assert generate_layout_id("My Setup!", existing_ids=["my_setup"]) == "my_setup_2"
    assert generate_layout_id("   ", existing_ids=[]) == "layout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_layout_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpk_deck.core.layout_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/layout_store.py
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

import yaml

from mpk_deck.config import LAYOUTS_PATH

logger = logging.getLogger(__name__)

ItemKind = Literal["program", "url"]


@dataclass(frozen=True)
class LayoutItem:
    kind: ItemKind
    rect: tuple[int, int, int, int]
    maximized: bool = False
    path: str = ""
    url: str = ""
    browser: str = ""
    title_match: str = ""


@dataclass
class Layout:
    name: str
    items: list[LayoutItem] = field(default_factory=list)


def generate_layout_id(name: str, existing_ids: Iterable[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "layout"
    existing = set(existing_ids)
    candidate, n = slug, 2
    while candidate in existing:
        candidate = f"{slug}_{n}"
        n += 1
    return candidate


def _parse_item(raw: dict) -> LayoutItem:
    kind = raw["kind"]
    if kind not in ("program", "url"):
        raise ValueError(f"unknown item kind: {kind!r}")
    rect = tuple(int(v) for v in raw["rect"])
    if len(rect) != 4:
        raise ValueError("rect must be 4 ints")
    return LayoutItem(
        kind=kind,
        rect=rect,  # type: ignore[arg-type]
        maximized=bool(raw.get("maximized", False)),
        path=str(raw.get("path", "")),
        url=str(raw.get("url", "")),
        browser=str(raw.get("browser", "")),
        title_match=str(raw.get("title_match", "")),
    )


def load_layouts(path: str | Path | None = None) -> dict[str, Layout]:
    path = Path(path) if path is not None else LAYOUTS_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        logger.warning("failed to parse %s, ignoring", path)
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("layouts"), dict):
        return {}
    result: dict[str, Layout] = {}
    for layout_id, raw in data["layouts"].items():
        try:
            items: list[LayoutItem] = []
            for i, raw_item in enumerate(raw.get("items", []) or []):
                try:
                    items.append(_parse_item(raw_item))
                except (KeyError, ValueError, TypeError) as exc:
                    logger.warning("layout %s item %d skipped: %s", layout_id, i, exc)
            result[layout_id] = Layout(name=str(raw.get("name", layout_id)), items=items)
        except (AttributeError, TypeError) as exc:
            logger.warning("layout %s skipped: %s", layout_id, exc)
    return result


def save_layouts(layouts: dict[str, Layout], path: str | Path | None = None) -> None:
    path = Path(path) if path is not None else LAYOUTS_PATH
    data = {
        "layouts": {
            layout_id: {
                "name": layout.name,
                "items": [
                    {k: (list(v) if isinstance(v, tuple) else v)
                     for k, v in asdict(item).items()
                     if v not in ("", 0, False) or k in ("kind", "rect")}
                    for item in layout.items
                ],
            }
            for layout_id, layout in layouts.items()
        }
    }
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
```

Note: the `asdict` filter keeps `kind` and `rect` always, and drops empty
`""`/`0`/`False` for the rest — check the round-trip test still passes (it does:
`maximized=False`, `url=""` etc. are re-defaulted on load).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_layout_store.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/layout_store.py tests/core/test_layout_store.py
git commit -m "feat(core): layout_store - Layout/LayoutItem model + atomic YAML persistence"
```

---

### Task 3: `core/browser_url.py`

**Files:**
- Create: `src/mpk_deck/core/browser_url.py`
- Test: `tests/core/test_browser_url.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `browser_kind(exe_path: str) -> str | None` — `"chrome"` / `"edge"` / `"firefox"` / `None`, by basename, case-insensitive.
  - `active_tab_url(hwnd: int) -> str | None` — best-effort UIA read of the active tab's address bar. `None` on any failure. **Manual-verify only** — no pytest for the UIA path.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_browser_url.py
from mpk_deck.core.browser_url import browser_kind


def test_browser_kind_recognises_the_chromium_browsers_and_firefox():
    assert browser_kind(r"C:\Program Files\Google\Chrome\Application\chrome.exe") == "chrome"
    assert browser_kind(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.EXE") == "edge"
    assert browser_kind(r"C:\Program Files\Mozilla Firefox\firefox.exe") == "firefox"


def test_browser_kind_is_none_for_non_browsers_and_blank():
    assert browser_kind(r"C:\Windows\System32\notepad.exe") is None
    assert browser_kind("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_browser_url.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/browser_url.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BROWSERS = {"chrome.exe": "chrome", "msedge.exe": "edge", "firefox.exe": "firefox"}


def browser_kind(exe_path: str) -> str | None:
    return _BROWSERS.get(Path(exe_path).name.lower()) if exe_path else None


def active_tab_url(hwnd: int) -> str | None:
    """Best-effort: walk the browser window's UI Automation tree for the address
    bar (a ControlType.Edit inside the toolbar) and read its value. Returns None
    on any COM/lookup failure - the caller falls back to a manual URL field.

    Not unit-tested (needs a live browser); verify manually per the spec."""
    try:
        import comtypes.client

        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CUIAutomation
            interface=comtypes.client.GetModule("UIAutomationCore.dll").IUIAutomation,
        )
        element = uia.ElementFromHandle(hwnd)
        if element is None:
            return None

        # find an Edit control anywhere under a ToolBar; prefer one whose name
        # looks like an address bar.
        UIA_EditControlTypeId = 50004
        UIA_ToolBarControlTypeId = 50021
        UIA_ControlTypePropertyId = 30003
        UIA_ValueValuePropertyId = 30045
        TreeScope_Descendants = 4

        cond_toolbar = uia.CreatePropertyCondition(UIA_ControlTypePropertyId, UIA_ToolBarControlTypeId)
        toolbars = element.FindAll(TreeScope_Descendants, cond_toolbar)
        cond_edit = uia.CreatePropertyCondition(UIA_ControlTypePropertyId, UIA_EditControlTypeId)
        candidates = []
        for i in range(toolbars.Length):
            edits = toolbars.GetElement(i).FindAll(TreeScope_Descendants, cond_edit)
            for j in range(edits.Length):
                candidates.append(edits.GetElement(j))
        if not candidates:
            edits = element.FindAll(TreeScope_Descendants, cond_edit)
            candidates = [edits.GetElement(j) for j in range(min(edits.Length, 8))]

        def _looks_like_address(e) -> bool:
            name = (e.CurrentName or "").lower()
            return any(t in name for t in ("address", "url", "주소", "검색", "search"))

        candidates.sort(key=lambda e: 0 if _looks_like_address(e) else 1)
        for e in candidates:
            value = e.GetCurrentPropertyValue(UIA_ValueValuePropertyId)
            if isinstance(value, str) and value.strip():
                return _normalise(value.strip())
        return None
    except Exception:
        logger.debug("active_tab_url failed for hwnd %s", hwnd, exc_info=True)
        return None


def _normalise(text: str) -> str | None:
    if " " in text or "." not in text:
        return None  # a search term, not a URL
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text
```

Note: the exact COM incantation (CLSID string, module interface) may need
adjusting for the installed comtypes — the implementer should verify against a
live Chrome window and tweak the tree walk. The contract (`str | None`, never
raises) is what matters.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_browser_url.py -q`
Expected: PASS (2 tests). The UIA path is unexercised by pytest — that is intended.

- [ ] **Step 5: Manual check + commit**

Manual: in a Python REPL with a Chrome window open, get its hwnd
(`win32gui.FindWindow(None, ...)` or enumerate) and call
`active_tab_url(hwnd)` — expect the current URL. Repeat for Edge. Record the
result in the commit message.

```bash
git add src/mpk_deck/core/browser_url.py tests/core/test_browser_url.py
git commit -m "feat(core): browser_url - browser_kind + best-effort UIA active-tab URL"
```

---

### Task 4: `core/window_layout.py` — pure helpers (`OpenWindow`, `_match`, `clamp_rect_to_monitors`)

**Files:**
- Create: `src/mpk_deck/core/window_layout.py`
- Test: `tests/core/test_window_layout.py`

**Interfaces:**
- Consumes: `LayoutItem` (Task 2), `browser_kind` (Task 3).
- Produces:
  - `OpenWindow` frozen dataclass: `hwnd: int`, `title: str`, `exe_path: str`, `rect: tuple[int,int,int,int]`, `maximized: bool`.
  - `match_window(item: LayoutItem, windows: list[OpenWindow]) -> int | None` — the hwnd of an already-open window for this item, or `None`. Rules per spec §9.3.
  - `clamp_rect_to_monitors(rect: tuple[int,int,int,int], monitors: list[tuple[int,int,int,int]]) -> tuple[int,int,int,int]` — move/shrink `rect` so it lies within the nearest monitor work-area.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_window_layout.py
from mpk_deck.core.layout_store import LayoutItem
from mpk_deck.core.window_layout import OpenWindow, clamp_rect_to_monitors, match_window


def _win(hwnd, title, exe, rect=(0, 0, 100, 100)):
    return OpenWindow(hwnd=hwnd, title=title, exe_path=exe, rect=rect, maximized=False)


def test_match_program_by_exe_basename():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1))
    wins = [_win(1, "x", "D:/other/Code.EXE"), _win(2, "y", "C:/z/notepad.exe")]
    assert match_window(item, wins) == 1


def test_match_program_prefers_title_match():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1), title_match="Project A")
    wins = [_win(1, "Project B - Code", "C:/Code.exe"), _win(2, "Project A - Code", "C:/Code.exe")]
    assert match_window(item, wins) == 2


def test_match_program_returns_none_when_absent():
    item = LayoutItem(kind="program", path="C:/a/Code.exe", rect=(0, 0, 1, 1))
    assert match_window(item, [_win(1, "x", "C:/notepad.exe")]) is None


def test_match_url_by_browser_and_title():
    item = LayoutItem(kind="url", url="https://x", browser="chrome", rect=(0, 0, 1, 1), title_match="Claude")
    wins = [_win(1, "GitHub - Chrome", "C:/chrome.exe"), _win(2, "Claude - Chrome", "C:/chrome.exe")]
    assert match_window(item, wins) == 2


def test_match_url_without_title_and_multiple_candidates_returns_none():
    item = LayoutItem(kind="url", url="https://x", browser="chrome", rect=(0, 0, 1, 1))
    wins = [_win(1, "A - Chrome", "C:/chrome.exe"), _win(2, "B - Chrome", "C:/chrome.exe")]
    assert match_window(item, wins) is None


def test_match_url_default_browser_matches_any_chromium():
    item = LayoutItem(kind="url", url="https://x", browser="default", rect=(0, 0, 1, 1), title_match="Claude")
    wins = [_win(1, "Claude - Edge", "C:/msedge.exe")]
    assert match_window(item, wins) == 1


def test_clamp_rect_keeps_a_fully_visible_rect():
    monitors = [(0, 0, 1920, 1080)]
    assert clamp_rect_to_monitors((100, 100, 800, 600), monitors) == (100, 100, 800, 600)


def test_clamp_rect_pulls_an_offscreen_rect_onto_the_nearest_monitor():
    monitors = [(0, 0, 1920, 1080)]
    x, y, w, h = clamp_rect_to_monitors((3000, 100, 800, 600), monitors)
    assert 0 <= x and x + w <= 1920 and 0 <= y and y + h <= 1080


def test_clamp_rect_shrinks_a_rect_bigger_than_the_monitor():
    monitors = [(0, 0, 1280, 720)]
    x, y, w, h = clamp_rect_to_monitors((0, 0, 4000, 4000), monitors)
    assert w <= 1280 and h <= 720
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/window_layout.py
import logging
from dataclasses import dataclass
from pathlib import Path

from mpk_deck.core.browser_url import browser_kind
from mpk_deck.core.layout_store import Layout, LayoutItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenWindow:
    hwnd: int
    title: str
    exe_path: str
    rect: tuple[int, int, int, int]
    maximized: bool


def _basename(path: str) -> str:
    return Path(path).name.lower()


def match_window(item: LayoutItem, windows: list[OpenWindow]) -> int | None:
    if item.kind == "program":
        target = _basename(item.path)
        cands = [w for w in windows if _basename(w.exe_path) == target]
    else:  # url
        want = item.browser
        def _ok(w: OpenWindow) -> bool:
            k = browser_kind(w.exe_path)
            return k is not None if want == "default" else k == want
        cands = [w for w in windows if _ok(w)]

    if not cands:
        return None
    if item.title_match:
        tm = item.title_match.lower()
        titled = [w for w in cands if tm in w.title.lower()]
        if titled:
            return titled[0].hwnd
        if item.kind == "url":
            return None  # a URL item must not hijack an unrelated browser window
        return cands[0].hwnd
    if item.kind == "url" and len(cands) > 1:
        return None  # ambiguous - open a fresh window instead
    return cands[0].hwnd


def clamp_rect_to_monitors(
    rect: tuple[int, int, int, int], monitors: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    if not monitors:
        return rect
    cx, cy = x + w / 2, y + h / 2

    def _dist(m: tuple[int, int, int, int]) -> float:
        mx, my, mw, mh = m
        mcx, mcy = mx + mw / 2, my + mh / 2
        return (cx - mcx) ** 2 + (cy - mcy) ** 2

    mx, my, mw, mh = min(monitors, key=_dist)
    w = min(w, mw)
    h = min(h, mh)
    x = max(mx, min(x, mx + mw - w))
    y = max(my, min(y, my + mh - h))
    return (x, y, w, h)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/window_layout.py tests/core/test_window_layout.py
git commit -m "feat(core): window_layout - OpenWindow, match_window, clamp_rect_to_monitors"
```

---

### Task 5: `core/window_layout.py` — `list_open_windows` + `capture_item`

**Files:**
- Modify: `src/mpk_deck/core/window_layout.py`
- Test: `tests/core/test_window_layout.py` (add)

**Interfaces:**
- Consumes: `OpenWindow` (Task 4), `browser_kind` + `active_tab_url` (Task 3).
- Produces:
  - `list_open_windows(*, resolver=None) -> list[OpenWindow]` — real top-level app windows (win32), excluding tool windows, cloaked windows, and mpk-deck's own. `resolver` seam returns a fake list for tests.
  - `capture_item(window: OpenWindow, *, url_reader=None) -> LayoutItem` — `url_reader` defaults to `browser_url.active_tab_url`; injected in tests.
  - `_short_title(title: str) -> str` — the fragment after the last `" - "`, capped at 40 chars.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_window_layout.py — add
from mpk_deck.core.window_layout import capture_item, list_open_windows


def test_list_open_windows_uses_the_injected_resolver():
    fake = [OpenWindow(1, "A", "C:/a.exe", (0, 0, 10, 10), False)]
    assert list_open_windows(resolver=lambda: fake) == fake


def test_capture_item_program_window():
    w = OpenWindow(9, "foo.py - Visual Studio Code", "C:/x/Code.exe", (10, 20, 800, 600), False)
    item = capture_item(w, url_reader=lambda hwnd: None)
    assert item.kind == "program"
    assert item.path == "C:/x/Code.exe"
    assert item.rect == (10, 20, 800, 600)
    assert item.title_match == "Visual Studio Code"


def test_capture_item_browser_window_with_a_readable_url():
    w = OpenWindow(9, "Claude - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900), True)
    item = capture_item(w, url_reader=lambda hwnd: "https://claude.ai/code")
    assert item.kind == "url"
    assert item.url == "https://claude.ai/code"
    assert item.browser == "chrome"
    assert item.maximized is True


def test_capture_item_browser_window_without_a_readable_url_emits_empty_url():
    w = OpenWindow(9, "New Tab - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900), False)
    item = capture_item(w, url_reader=lambda hwnd: None)
    assert item.kind == "url"
    assert item.url == ""
    assert item.browser == "chrome"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: FAIL — `ImportError: cannot import name 'capture_item'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/window_layout.py — add

_MAX_TITLE = 40


def _short_title(title: str) -> str:
    frag = title.rsplit(" - ", 1)[-1].strip()
    return frag[:_MAX_TITLE]


def list_open_windows(*, resolver=None) -> list["OpenWindow"]:
    if resolver is not None:
        return resolver()
    return _win32_list_open_windows()


def _win32_list_open_windows() -> list["OpenWindow"]:
    import ctypes
    from ctypes import wintypes

    import win32con
    import win32gui
    import win32process

    own_pid = ctypes.windll.kernel32.GetCurrentProcessId()
    results: list[OpenWindow] = []

    def _exe_path(pid: int) -> str:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value
            return ""
        finally:
            ctypes.windll.kernel32.CloseHandle(h)

    def _cloaked(hwnd: int) -> bool:
        DWMWA_CLOAKED = 14
        val = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            return False
        return val.value != 0

    def _cb(hwnd, _lparam):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_TOOLWINDOW:
            return True
        if _cloaked(hwnd):
            return True
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left <= 0 or bottom - top <= 0:
            return True
        _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == own_pid:
            return True
        placement = win32gui.GetWindowPlacement(hwnd)
        results.append(
            OpenWindow(
                hwnd=hwnd,
                title=title,
                exe_path=_exe_path(pid),
                rect=(left, top, right - left, bottom - top),
                maximized=placement[1] == win32con.SW_SHOWMAXIMIZED,
            )
        )
        return True

    win32gui.EnumWindows(_cb, None)
    return results


def capture_item(window: "OpenWindow", *, url_reader=None) -> LayoutItem:
    reader = url_reader if url_reader is not None else _default_url_reader
    kind = browser_kind(window.exe_path)
    if kind is not None:
        url = reader(window.hwnd) or ""
        return LayoutItem(
            kind="url", url=url, browser=kind, rect=window.rect,
            maximized=window.maximized, title_match=_short_title(window.title),
        )
    return LayoutItem(
        kind="program", path=window.exe_path, rect=window.rect,
        maximized=window.maximized, title_match=_short_title(window.title),
    )


def _default_url_reader(hwnd: int) -> str | None:
    from mpk_deck.core.browser_url import active_tab_url

    return active_tab_url(hwnd)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: PASS (all)

- [ ] **Step 5: Manual check + commit**

Manual: `python -c "from mpk_deck.core.window_layout import list_open_windows; [print(w.title, '|', w.exe_path) for w in list_open_windows()]"` — expect your real open windows, no mpk-deck, no tooltips/ghosts.

```bash
git add src/mpk_deck/core/window_layout.py tests/core/test_window_layout.py
git commit -m "feat(core): window_layout - list_open_windows + capture_item"
```

---

### Task 6: `core/window_layout.py` — `position_window`, `restore_layout`

**Files:**
- Modify: `src/mpk_deck/core/window_layout.py`
- Test: `tests/core/test_window_layout.py` (add)

**Interfaces:**
- Consumes: `Layout` (Task 2), `match_window` + `clamp_rect_to_monitors` + `list_open_windows` (Tasks 4-5).
- Produces:
  - `position_window(hwnd: int, rect: tuple[int,int,int,int], maximized: bool) -> None` — clamps then places via `SetWindowPlacement` + `SetWindowPos`; never raises.
  - `restore_layout(layout: Layout, *, window_lister=None, launcher=None, positioner=None, sleep=None) -> None` — the orchestration in spec §9.2. Fully covered with injected seams.
  - `_default_launch(item: LayoutItem) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_window_layout.py — add
from mpk_deck.core.layout_store import Layout, LayoutItem
from mpk_deck.core.window_layout import restore_layout


def test_restore_positions_an_already_open_window_and_does_not_launch():
    item = LayoutItem(kind="program", path="C:/Code.exe", rect=(10, 10, 800, 600))
    open_win = OpenWindow(42, "Code", "C:/Code.exe", (0, 0, 1, 1), False)
    launched, positioned = [], []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lambda: [open_win],
        launcher=lambda it: launched.append(it),
        positioner=lambda hwnd, rect, mx: positioned.append((hwnd, rect, mx)),
        sleep=lambda _s: None,
    )
    assert launched == []
    assert positioned and positioned[0][0] == 42
    assert positioned[0][1] == (10, 10, 800, 600)


def test_restore_launches_then_polls_then_positions_a_missing_item():
    item = LayoutItem(kind="program", path="C:/Code.exe", rect=(5, 5, 400, 300))
    calls = {"list": 0}
    appears = OpenWindow(99, "Code", "C:/Code.exe", (0, 0, 1, 1), False)

    def lister():
        calls["list"] += 1
        return [] if calls["list"] <= 2 else [appears]  # shows up on the 3rd poll

    launched, positioned = [], []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lister,
        launcher=lambda it: launched.append(it),
        positioner=lambda hwnd, rect, mx: positioned.append(hwnd),
        sleep=lambda _s: None,
    )
    assert launched == [item]
    assert positioned == [99, 99]  # positioned twice (immediately + after settle)


def test_restore_logs_and_continues_when_a_window_never_appears(caplog):
    item = LayoutItem(kind="program", path="C:/Missing.exe", rect=(0, 0, 1, 1))
    positioned = []
    restore_layout(
        Layout(name="L", items=[item]),
        window_lister=lambda: [],
        launcher=lambda it: None,
        positioner=lambda *a: positioned.append(a),
        sleep=lambda _s: None,
    )
    assert positioned == []
    assert "no window" in caplog.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: FAIL — `ImportError: cannot import name 'restore_layout'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/window_layout.py — add
import subprocess
import time as _time

_POLL_TIMEOUT_S = 8.0
_POLL_INTERVAL_S = 0.25
_SETTLE_S = 0.15


def position_window(hwnd: int, rect: tuple[int, int, int, int], maximized: bool) -> None:
    try:
        import win32con
        import win32gui

        monitors = [m[:4] for m in _monitor_work_areas()]
        x, y, w, h = clamp_rect_to_monitors(rect, monitors) if monitors else rect
        show = win32con.SW_SHOWMAXIMIZED if maximized else win32con.SW_SHOWNORMAL
        win32gui.SetWindowPlacement(hwnd, (0, show, (-1, -1), (-1, -1), (x, y, x + w, y + h)))
        if not maximized:
            win32gui.SetWindowPos(
                hwnd, 0, x, y, w, h,
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
            )
    except Exception:
        logger.warning("position_window failed for hwnd %s", hwnd, exc_info=True)


def _monitor_work_areas() -> list[tuple[int, int, int, int]]:
    try:
        import win32api

        areas = []
        for handle, _dc, _rect in win32api.EnumDisplayMonitors():
            info = win32api.GetMonitorInfo(handle)
            l, t, r, b = info["Work"]
            areas.append((l, t, r - l, b - t))
        return areas
    except Exception:
        return []


def _default_launch(item: LayoutItem) -> None:
    from pathlib import Path as _P

    try:
        if item.kind == "program":
            if item.path and _P(item.path).exists():
                subprocess.Popen([item.path])
            else:
                logger.warning("restore: program not found: %s", item.path)
        else:
            if not item.url:
                logger.warning("restore: url item has no url, skipping launch")
                return
            exe = _resolve_browser_exe(item.browser)
            if exe:
                subprocess.Popen([exe, "--new-window", item.url])
            else:
                import webbrowser

                webbrowser.open(item.url)
    except Exception:
        logger.warning("restore: launch failed for %r", item, exc_info=True)


def _resolve_browser_exe(browser: str) -> str | None:
    if browser == "default":
        return None
    from mpk_deck.core.program_finder import list_installed_programs

    want = {"chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe"}.get(browser)
    if not want:
        return None
    for p in list_installed_programs():
        if _basename(p.path) == want:
            return p.path
    for guess in (
        rf"C:\Program Files\Google\Chrome\Application\chrome.exe",
        rf"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        rf"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if _basename(guess) == want and _P_exists(guess):
            return guess
    return None


def _P_exists(path: str) -> bool:
    from pathlib import Path as _P

    return _P(path).exists()


def restore_layout(
    layout: Layout,
    *,
    window_lister=None,
    launcher=None,
    positioner=None,
    sleep=None,
) -> None:
    lister = window_lister or list_open_windows
    launch = launcher or _default_launch
    place = positioner or position_window
    nap = sleep or _time.sleep

    for i, item in enumerate(layout.items):
        hwnd = match_window(item, lister())
        if hwnd is None:
            launch(item)
            nap(0.2 * i)
            hwnd = _poll_for_window(item, lister, nap)
        if hwnd is None:
            logger.warning("restore_layout: no window for %r", item)
            continue
        place(hwnd, item.rect, item.maximized)
        nap(_SETTLE_S)
        place(hwnd, item.rect, item.maximized)


def _poll_for_window(item: LayoutItem, lister, nap) -> int | None:
    waited = 0.0
    while waited < _POLL_TIMEOUT_S:
        hwnd = match_window(item, lister())
        if hwnd is not None:
            return hwnd
        nap(_POLL_INTERVAL_S)
        waited += _POLL_INTERVAL_S
    return None
```

Note: the test injects `sleep=lambda _s: None`, so the poll loop runs
`_POLL_TIMEOUT_S / _POLL_INTERVAL_S` = 32 iterations instantly when a window
never appears — fine.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_window_layout.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/window_layout.py tests/core/test_window_layout.py
git commit -m "feat(core): window_layout - position_window + restore_layout orchestration"
```

---

### Task 7: `apply_layout` handler + engine registration

**Files:**
- Modify: `src/mpk_deck/core/handlers.py`
- Modify: `src/mpk_deck/ui/main_window.py` (`build_action_engine`)
- Test: `tests/core/test_handlers.py` (add)

**Interfaces:**
- Consumes: `load_layouts` (Task 2), `restore_layout` (Task 6).
- Produces:
  - `handlers.apply_layout(params: dict, *, loader=None, restore=None) -> None` — `loader` defaults to `layout_store.load_layouts`, `restore` defaults to `_spawn_restore` (daemon thread → `window_layout.restore_layout`). Missing/blank `layout_id` or unknown layout → `logger` + return, no raise.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_handlers.py — add
from mpk_deck.core.handlers import apply_layout
from mpk_deck.core.layout_store import Layout


def test_apply_layout_restores_the_named_layout():
    layout = Layout(name="L", items=[])
    got = []
    apply_layout(
        {"layout_id": "abc"},
        loader=lambda: {"abc": layout},
        restore=lambda lo: got.append(lo),
    )
    assert got == [layout]


def test_apply_layout_no_id_is_a_noop(caplog):
    called = []
    apply_layout({}, loader=lambda: {}, restore=lambda lo: called.append(lo))
    assert called == []


def test_apply_layout_unknown_id_is_a_noop(caplog):
    called = []
    apply_layout(
        {"layout_id": "missing"}, loader=lambda: {}, restore=lambda lo: called.append(lo)
    )
    assert called == []
    assert "not found" in caplog.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_handlers.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_layout'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/handlers.py — add
import threading


def apply_layout(params: dict, *, loader=None, restore=None) -> None:
    """Restore a saved workspace layout. Runs the actual work on a daemon thread
    (it launches apps and polls for windows for several seconds) so the GUI
    thread that dispatched this handler is never blocked."""
    layout_id = params.get("layout_id")
    if not layout_id:
        logger.info("apply_layout: no layout bound")
        return
    load = loader or _default_layout_loader
    layout = load().get(layout_id)
    if layout is None:
        logger.warning("apply_layout: layout %r not found", layout_id)
        return
    (restore or _spawn_restore)(layout)


def _default_layout_loader():
    from mpk_deck.core.layout_store import load_layouts

    return load_layouts()


def _spawn_restore(layout) -> None:
    from mpk_deck.core.window_layout import restore_layout

    threading.Thread(target=restore_layout, args=(layout,), daemon=True).start()
```

```python
# src/mpk_deck/ui/main_window.py — in build_action_engine, add to the imports line
from mpk_deck.core.handlers import (
    apply_layout, focus_window, launch_program, open_url,
    scroll_horizontal, scroll_vertical, set_system_volume,
)
# ...and inside build_action_engine, next to the other register_trigger calls:
    engine.register_trigger("apply_layout", apply_layout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_handlers.py -q && python -m pytest -q`
Expected: PASS; full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/handlers.py src/mpk_deck/ui/main_window.py tests/core/test_handlers.py
git commit -m "feat(core): apply_layout trigger handler (restore on a worker thread)"
```

---

### Task 8: `nl_action` coverage for `apply_layout`

**Files:**
- Modify: `src/mpk_deck/core/nl_action.py`
- Test: `tests/core/test_nl_action.py` (add)

**Interfaces:**
- Consumes: `load_layouts` (Task 2).
- Produces: `parse_nl_action` can return `Binding(action="apply_layout", params={"layout_id": <id>})` when the model picks `apply_layout` with a `layout_name` that resolves against `load_layouts()` (exact, then case-insensitive). No match → `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_nl_action.py — add. Reuse the fake-client pattern already in this file.
from mpk_deck.core.nl_action import parse_nl_action


class _FakeBlock:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class _FakeResp:
    def __init__(self, data):
        self.content = [_FakeBlock(data)]


class _FakeClient:
    def __init__(self, data):
        self._data = data
        self.messages = self

    def create(self, **_kw):
        return _FakeResp(self._data)


def test_nl_action_resolves_a_layout_name(monkeypatch):
    from mpk_deck.core.layout_store import Layout
    import mpk_deck.core.nl_action as nl

    monkeypatch.setattr(nl, "load_layouts", lambda: {"coding": Layout(name="코딩 셋업", items=[])})
    binding = parse_nl_action(
        "코딩 레이아웃 열어", [], client=_FakeClient({"action": "apply_layout", "layout_name": "코딩 셋업"})
    )
    assert binding is not None
    assert binding.action == "apply_layout"
    assert binding.params == {"layout_id": "coding"}


def test_nl_action_unknown_layout_name_returns_none(monkeypatch):
    import mpk_deck.core.nl_action as nl

    monkeypatch.setattr(nl, "load_layouts", lambda: {})
    binding = parse_nl_action(
        "x", [], client=_FakeClient({"action": "apply_layout", "layout_name": "nope"})
    )
    assert binding is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_nl_action.py -q`
Expected: FAIL — model output `apply_layout` not in `ACTION_TYPE`, `_to_binding` returns `None` (or `AttributeError` on `load_layouts`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/core/nl_action.py

# add the import near the top
from mpk_deck.core.layout_store import load_layouts

# add to ACTION_TYPE
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
    "apply_layout": "trigger",
}

# add to _TOOL["input_schema"]["properties"]
    "layout_name": {"type": "string", "description": "Required for apply_layout; the name of a saved layout."},

# in _to_binding, add a branch before the final `else`
    elif action == "apply_layout":
        name = (data.get("layout_name") or "").strip()
        layouts = load_layouts()
        match = next((lid for lid, lo in layouts.items() if lo.name == name), None)
        if match is None:
            match = next((lid for lid, lo in layouts.items() if lo.name.lower() == name.lower()), None)
        if match is None:
            return None
        params = {"layout_id": match}
```

Also update `_TOOL["description"]`'s enum reference if it hardcodes the action list.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_nl_action.py -q && python -m pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/nl_action.py tests/core/test_nl_action.py
git commit -m "feat(core): nl_action can bind apply_layout by layout name"
```

---

## Self-Review

**Spec coverage:**
- §5.1 `layouts.yaml` schema → Task 2 ✓
- §5.2 `layout_store` → Task 2 ✓
- §5.3 `Binding` `apply_layout` action + engine registration → Task 7 (UI-side additions to ACTION_CHOICES etc. are in the **UI plan**) ✓
- §6 `list_open_windows` / `capture_item` → Tasks 4-5 ✓
- §7 `browser_kind` / `active_tab_url` → Task 3 ✓
- §8.3 `nl_action` → Task 8 ✓
- §9 restore (`apply_layout` handler, `restore_layout`, `_match`, `position_window`, `clamp_rect_to_monitors`, `_default_launch`) → Tasks 4, 6, 7 ✓
- §10 `user_data_dir()` / `LAYOUTS_PATH` → Task 1 ✓
- §11 testing → each task's Steps ✓ (UIA + `list_open_windows` + `position_window` are manual, flagged)
- §12 risks → clamp (Task 4), double-position (Task 6), per-window try/except (Task 6), worker thread (Task 7), `%APPDATA%` fallback (Task 1) ✓

**Placeholder scan:** the two "note" paragraphs (Task 3 COM incantation, Task 6 poll-count) describe real latitude for the implementer, not deferred work — acceptable. No TBD/TODO.

**Type consistency:** `match_window` (Task 4) used by `restore_layout` (Task 6) ✓. `OpenWindow` fields consistent across Tasks 4-6 ✓. `LayoutItem`/`Layout` from Task 2 used everywhere ✓. `capture_item(window, *, url_reader=)` / `list_open_windows(*, resolver=)` seam names match the tests ✓. `apply_layout(params, *, loader=, restore=)` (Task 7) matches its test ✓.

**Gaps:** none found. UI-side wiring (ACTION_CHOICES, param page, capture dialog, view labels, MainWindow layout loading) is deliberately the separate **UI plan** — this plan is independently testable (all `core/` tests pass, handler registered).
