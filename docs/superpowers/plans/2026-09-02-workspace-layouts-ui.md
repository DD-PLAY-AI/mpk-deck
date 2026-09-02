# Workspace Layouts — UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the config dialog a "레이아웃" action — pick a saved layout or capture a new one from a checklist of open windows — and show the bound layout's name on the deck.

**Architecture:** `apply_layout` joins the existing action set in `ActionConfigDialog` with a param page (dropdown of saved layouts + "새로 저장…" / "편집…" buttons). A new frameless glass `LayoutCaptureDialog` lists open windows with per-row URL fields. `action_icons` gets a "scene" glyph and resolves the layout name for the deck label; `MiniView`/`ExpandedView`/`MainWindow` thread the loaded layouts through `update_bindings`.

**Tech Stack:** PySide6 QtWidgets, the `core/` modules from the Core plan, pytest (offscreen Qt smoke tests).

**Spec:** `docs/superpowers/specs/2026-09-02-workspace-layouts-design.md`

**Depends on:** `docs/superpowers/plans/2026-09-02-workspace-layouts-core.md` — land and test that first. This plan consumes `core.layout_store` (`Layout`, `LayoutItem`, `load_layouts`, `save_layouts`, `generate_layout_id`) and `core.window_layout` (`list_open_windows`, `capture_item`).

## Global Constraints

- Windows-only imports stay lazy. Qt widgets are smoke-tested offscreen (`QT_QPA_PLATFORM=offscreen`), not unit-tested per project policy — but pure helpers and `result_binding()`-style methods ARE tested.
- Match the existing dialog's glass style: reuse `action_config_dialog._dialog_qss` (frameless, `WA_TranslucentBackground`, accent-derived, light/dark via a `dark: bool` arg). No hard-coded hex.
- `ActionConfigDialog`'s public interface is frozen: `result_binding()`, `result_bank_name()`, constructor signature. `apply_layout` is a **normal rebindable action**, not locked like `switch_bank`.
- Korean UI strings; keep technical/CLI terms verbatim.
- Tests: `cd C:\DC\DD\mpk-deck && python -m pytest -q`. `tests/` mirrors `src/`.

---

### Task 1: `action_icons` — layout glyph + label resolution

**Files:**
- Modify: `src/mpk_deck/ui/action_icons.py`
- Test: `tests/ui/test_action_icons.py` (add)

**Interfaces:**
- Consumes: `core.layout_store.Layout`.
- Produces:
  - `ACTION_KO_LABEL["apply_layout"] == "레이아웃"`.
  - `_ACTION_SVG["apply_layout"]` and `_ACTION_SVG_KNOB["apply_layout"]` (a small grid-of-rectangles "scene" glyph, `{accent}` + `{neutral}`).
  - `action_label(binding, bank_names=None, layouts=None)` — new optional `layouts: dict[str, Layout]`; for `apply_layout` returns `layouts[binding.params["layout_id"]].name` when resolvable, else `"레이아웃"`. Existing `bank_names` behaviour unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_action_icons.py — add
def test_action_label_resolves_a_layout_name():
    from mpk_deck.core.action_registry import Binding
    from mpk_deck.core.layout_store import Layout
    from mpk_deck.ui.action_icons import action_label

    b = Binding("pad_1", "trigger", "apply_layout", {"layout_id": "coding"})
    assert action_label(b, layouts={"coding": Layout(name="코딩 셋업", items=[])}) == "코딩 셋업"
    assert action_label(b) == "레이아웃"  # unresolved


def test_apply_layout_pixmap_is_non_null():
    from mpk_deck.core.action_registry import Binding
    from mpk_deck.ui.action_icons import action_pixmap
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    pm = action_pixmap(Binding("c", "trigger", "apply_layout", {}), 48, "#3a6df0")
    assert not pm.isNull()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ui/test_action_icons.py -q`
Expected: FAIL — `action_label` has no `layouts` kwarg / `apply_layout` missing from `_ACTION_SVG` (falls back to `launch_program` glyph, `"레이아웃"` label missing).

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/ui/action_icons.py

# ACTION_KO_LABEL: add
    "apply_layout": "레이아웃",

# _ACTION_SVG: add (a 2x2 grid of rounded rects = a "scene")
    "apply_layout": (
        '<rect x="12" y="12" width="18" height="18" rx="3" fill="none" stroke="{neutral}" stroke-width="4.5"/>'
        '<rect x="34" y="12" width="18" height="18" rx="3" fill="none" stroke="{neutral}" stroke-width="4.5"/>'
        '<rect x="12" y="34" width="18" height="18" rx="3" fill="none" stroke="{neutral}" stroke-width="4.5"/>'
        '<rect x="34" y="34" width="18" height="18" rx="3" fill="{accent}" stroke="{accent}" stroke-width="4.5"/>'
    ),

# _ACTION_SVG_KNOB: add
    "apply_layout": (
        '<rect x="14" y="14" width="16" height="16" rx="3" fill="none" stroke="{accent}" stroke-width="5"/>'
        '<rect x="34" y="14" width="16" height="16" rx="3" fill="none" stroke="{accent}" stroke-width="5"/>'
        '<rect x="14" y="34" width="16" height="16" rx="3" fill="none" stroke="{accent}" stroke-width="5"/>'
        '<rect x="34" y="34" width="16" height="16" rx="3" fill="{accent}" stroke="{accent}" stroke-width="5"/>'
    ),
```

```python
# action_label signature + branch
def action_label(binding, bank_names=None, layouts=None) -> str:
    if binding.label:
        return binding.label
    if binding.action == "launch_program":
        path = binding.params.get("path", "")
        return program_name_from_path(path) if path else ACTION_KO_LABEL["launch_program"]
    if binding.action == "switch_bank":
        bank_id = binding.params.get("bank_id", "")
        return (bank_names or {}).get(bank_id) or ACTION_KO_LABEL["switch_bank"]
    if binding.action == "apply_layout":
        layout = (layouts or {}).get(binding.params.get("layout_id", ""))
        return layout.name if layout is not None else ACTION_KO_LABEL["apply_layout"]
    return ACTION_KO_LABEL.get(binding.action, binding.action)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ui/test_action_icons.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/action_icons.py tests/ui/test_action_icons.py
git commit -m "feat(ui): action_icons - apply_layout glyph + layout-name label"
```

---

### Task 2: thread `layouts` through the deck views

**Files:**
- Modify: `src/mpk_deck/ui/mini_view.py`, `src/mpk_deck/ui/expanded_view.py`, `src/mpk_deck/ui/main_window.py`
- Test: `tests/ui/test_main_window_threading.py` (add)

**Interfaces:**
- Consumes: `action_label(..., layouts=)` (Task 1), `core.layout_store.load_layouts`.
- Produces:
  - `MiniView.update_bindings(bindings, bank_names=None, layouts=None)` and `ExpandedView.update_bindings(bindings, bank_names=None, layouts=None)` — new optional `layouts`, stored as `self._layouts` and passed to every `action_label(...)` call in that method (and re-passed from `set_accent`).
  - `MainWindow` loads `layout_store.load_layouts()` into `self._layouts` at init, passes it to both `update_bindings` calls at all three sites (init, `_apply_bank_change`, `_sync_after_binding_change`), and reloads it after a layout is saved (Task 4 wires the save signal).

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_main_window_threading.py — add
def test_apply_layout_pad_shows_the_layout_name(tmp_path, monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    import mpk_deck.ui.main_window as mw
    from mpk_deck.core.action_registry import Binding
    from mpk_deck.core.layout_store import Layout

    monkeypatch.setattr(mw, "_load_layouts_safe", lambda: {"coding": Layout(name="코딩 셋업", items=[])}, raising=False)
    monkeypatch.setattr("mpk_deck.ui.main_window.load_layouts", lambda: {"coding": Layout(name="코딩 셋업", items=[])})
    import unittest.mock as m
    with m.patch.object(mw.MPKController, "start", lambda self: False):
        window = MainWindow()
    window._mini_view.update_bindings(
        {"pad_1": Binding("pad_1", "trigger", "apply_layout", {"layout_id": "coding"})},
        {}, window._layouts,
    )
    assert window._mini_view._pads["pad_1"]._binding_label == "코딩 셋업"
    window.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ui/test_main_window_threading.py -q`
Expected: FAIL — `MainWindow` has no `_layouts`; `update_bindings` has no `layouts` param.

- [ ] **Step 3: Write minimal implementation**

`mini_view.py` / `expanded_view.py` — in `update_bindings`, add `layouts=None`, store `self._layouts = dict(layouts or {})`, and change every `action_label(binding, self._bank_names)` to `action_label(binding, self._bank_names, self._layouts)`. In `__init__` add `self._layouts: dict = {}`. In `set_accent`, pass `self._layouts` to the `update_bindings` self-call.

`main_window.py`:

```python
# import
from mpk_deck.core.layout_store import load_layouts

# in __init__, after self._bank_names = ...
self._layouts = load_layouts()

# every update_bindings call (3 sites, both views) gains a third arg:
self._mini_view.update_bindings(self._bindings, self._bank_names, self._layouts)
self._expanded_view.update_bindings(self._bindings, self._bank_names, self._layouts)

# add a helper used by Task 4 after a layout save:
def _reload_layouts(self) -> None:
    self._layouts = load_layouts()
    self._mini_view.update_bindings(self._bindings, self._bank_names, self._layouts)
    self._expanded_view.update_bindings(self._bindings, self._bank_names, self._layouts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q`
Expected: full suite green (existing `update_bindings` callers still work — `layouts` is optional).

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/mini_view.py src/mpk_deck/ui/expanded_view.py src/mpk_deck/ui/main_window.py tests/ui/test_main_window_threading.py
git commit -m "feat(ui): thread saved layouts through update_bindings for the deck label"
```

---

### Task 3: `LayoutCaptureDialog`

**Files:**
- Create: `src/mpk_deck/ui/layout_capture_dialog.py`
- Test: `tests/ui/test_layout_capture_dialog.py`

**Interfaces:**
- Consumes: `core.window_layout.list_open_windows` + `capture_item`, `core.layout_store` (`Layout`, `LayoutItem`, `generate_layout_id`, `save_layouts`, `load_layouts`), `action_config_dialog._dialog_qss`.
- Produces:
  - `LayoutCaptureDialog(existing_id: str | None = None, accent_hex=ACCENT_HEX, dark=True, parent=None, *, window_lister=None, url_reader=None)`.
  - `.result_layout_id() -> str | None` — the id it saved (new or overwritten), or `None` if cancelled.
  - `_rows: list[_CaptureRow]` — each has `.checkbox`, `.item: LayoutItem`, `.url_edit` (None for non-browser rows).
  - `_build_layout() -> Layout` — from ticked rows, applying the current URL-field text to browser rows.
  - `_can_save() -> bool` — False if any ticked browser row has an empty URL, or the name is blank.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_layout_capture_dialog.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from mpk_deck.core.window_layout import OpenWindow
from mpk_deck.ui.layout_capture_dialog import LayoutCaptureDialog


@pytest.fixture(autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


_WINDOWS = [
    OpenWindow(1, "foo.py - Visual Studio Code", "C:/x/Code.exe", (10, 10, 800, 600), False),
    OpenWindow(2, "Claude - Google Chrome", "C:/x/chrome.exe", (0, 0, 500, 900), True),
    OpenWindow(3, "New Tab - Google Chrome", "C:/x/chrome.exe", (100, 0, 500, 900), False),
]


def _dialog(url_for=None, tmp_path=None, monkeypatch=None):
    if tmp_path is not None:
        monkeypatch.setattr(
            "mpk_deck.ui.layout_capture_dialog.LAYOUTS_PATH", tmp_path / "layouts.yaml"
        )
    return LayoutCaptureDialog(
        window_lister=lambda: _WINDOWS,
        url_reader=url_for or (lambda hwnd: "https://claude.ai" if hwnd == 2 else None),
    )


def test_rows_are_one_per_open_window():
    d = _dialog()
    assert len(d._rows) == 3
    assert d._rows[0].item.kind == "program"
    assert d._rows[1].item.kind == "url" and d._rows[1].url_edit is not None


def test_browser_row_prefills_the_url_from_the_reader():
    d = _dialog()
    assert d._rows[1].url_edit.text() == "https://claude.ai"
    assert d._rows[2].url_edit.text() == ""


def test_cannot_save_a_ticked_browser_row_with_no_url():
    d = _dialog()
    d._name_edit.setText("코딩")
    for r in d._rows:
        r.checkbox.setChecked(True)  # row 3 has no URL
    assert d._can_save() is False
    d._rows[2].checkbox.setChecked(False)
    assert d._can_save() is True


def test_build_layout_from_ticked_rows(tmp_path, monkeypatch):
    d = _dialog(tmp_path=tmp_path, monkeypatch=monkeypatch)
    d._name_edit.setText("코딩 셋업")
    d._rows[0].checkbox.setChecked(True)
    d._rows[1].checkbox.setChecked(True)
    layout = d._build_layout()
    assert layout.name == "코딩 셋업"
    assert [i.kind for i in layout.items] == ["program", "url"]
    assert layout.items[1].url == "https://claude.ai"


def test_save_persists_and_result_layout_id_is_set(tmp_path, monkeypatch):
    d = _dialog(tmp_path=tmp_path, monkeypatch=monkeypatch)
    d._name_edit.setText("코딩")
    d._rows[0].checkbox.setChecked(True)
    d._on_save()
    from mpk_deck.core.layout_store import load_layouts
    saved = load_layouts(tmp_path / "layouts.yaml")
    assert d.result_layout_id() in saved
    assert saved[d.result_layout_id()].name == "코딩"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ui/test_layout_capture_dialog.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/mpk_deck/ui/layout_capture_dialog.py
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from mpk_deck.config import ACCENT_HEX, LAYOUTS_PATH
from mpk_deck.core.layout_store import Layout, generate_layout_id, load_layouts, save_layouts
from mpk_deck.core.window_layout import capture_item, list_open_windows
from mpk_deck.ui.action_config_dialog import _dialog_qss


@dataclass
class _CaptureRow:
    checkbox: QCheckBox
    item: "object"          # LayoutItem, refreshed by _build_layout for browser rows
    url_edit: "QLineEdit | None"
    window: "object"        # OpenWindow


class LayoutCaptureDialog(QDialog):
    def __init__(self, existing_id=None, accent_hex=ACCENT_HEX, dark=True, parent=None,
                 *, window_lister=None, url_reader=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(520)
        self._existing_id = existing_id
        self._result_id: str | None = None
        self._url_reader = url_reader

        card = QWidget(self)
        card.setObjectName("card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(_dialog_qss(accent_hex, dark))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        root = QVBoxLayout(card)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        heading = QLabel("레이아웃 저장")
        heading.setObjectName("heading")
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("레이아웃 이름")
        root.addWidget(heading)
        root.addWidget(self._name_edit)
        root.addWidget(QLabel("포함할 창", objectName="fieldLabel"))

        self._rows: list[_CaptureRow] = []
        rows_container = QWidget()
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)
        for w in (window_lister or list_open_windows)():
            row = self._make_row(w)
            self._rows.append(row)
            rows_layout.addWidget(self._row_widget(row))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(rows_container)
        scroll.setMinimumHeight(220)
        root.addWidget(scroll, stretch=1)

        self._error = QLabel("")
        self._error.setObjectName("nlError")
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setObjectName("primary")
        save.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        if existing_id is not None:
            existing = load_layouts().get(existing_id)
            if existing is not None:
                self._name_edit.setText(existing.name)

    def _make_row(self, window) -> _CaptureRow:
        reader = self._url_reader
        item = capture_item(window, url_reader=reader) if reader is not None else capture_item(window)
        cb = QCheckBox()
        url_edit = None
        if item.kind == "url":
            url_edit = QLineEdit(item.url)
            url_edit.setPlaceholderText("https://…  (URL을 못 읽었으면 직접 입력)")
        return _CaptureRow(checkbox=cb, item=item, url_edit=url_edit, window=window)

    def _row_widget(self, row: _CaptureRow) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(row.checkbox)
        title = QLabel(row.window.title)
        title.setMinimumWidth(160)
        lay.addWidget(title)
        if row.url_edit is not None:
            lay.addWidget(row.url_edit, stretch=1)
        else:
            dims = QLabel(f"{row.window.rect[2]}×{row.window.rect[3]}")
            dims.setObjectName("hint")
            lay.addWidget(dims)
            lay.addStretch(1)
        return w

    def _can_save(self) -> bool:
        if not self._name_edit.text().strip():
            return False
        for r in self._rows:
            if r.checkbox.isChecked() and r.url_edit is not None and not r.url_edit.text().strip():
                return False
        return True

    def _build_layout(self) -> Layout:
        from mpk_deck.core.layout_store import LayoutItem

        items = []
        for r in self._rows:
            if not r.checkbox.isChecked():
                continue
            item = r.item
            if r.url_edit is not None:
                item = LayoutItem(
                    kind="url", url=r.url_edit.text().strip(), browser=item.browser,
                    rect=item.rect, maximized=item.maximized, title_match=item.title_match,
                )
            items.append(item)
        return Layout(name=self._name_edit.text().strip(), items=items)

    def _on_save(self) -> None:
        if not self._can_save():
            self._error.setText("이름을 입력하고, 체크한 브라우저 창엔 URL을 채워주세요.")
            return
        layouts = load_layouts()
        layout = self._build_layout()
        layout_id = self._existing_id or generate_layout_id(layout.name, layouts.keys())
        layouts[layout_id] = layout
        save_layouts(layouts)
        self._result_id = layout_id
        self.accept()

    def result_layout_id(self) -> str | None:
        return self._result_id
```

Note: `save_layouts()` / `load_layouts()` with no path use `LAYOUTS_PATH`;
tests monkeypatch `layout_capture_dialog.LAYOUTS_PATH` — but `save_layouts`
reads `layout_store.LAYOUTS_PATH`. **Fix:** have `_on_save` call
`save_layouts(layouts, LAYOUTS_PATH)` and `load_layouts(LAYOUTS_PATH)`
explicitly, importing `LAYOUTS_PATH` into this module so the monkeypatch on
this module's name takes effect. Adjust the test's monkeypatch target if you
route it differently — keep them consistent.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ui/test_layout_capture_dialog.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/layout_capture_dialog.py tests/ui/test_layout_capture_dialog.py
git commit -m "feat(ui): LayoutCaptureDialog - checklist of open windows -> saved layout"
```

---

### Task 4: `apply_layout` action + param page in `ActionConfigDialog`

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`
- Test: `tests/ui/test_action_config_dialog.py` (add)

**Interfaces:**
- Consumes: `LayoutCaptureDialog` (Task 3), `core.layout_store.load_layouts`.
- Produces:
  - `ACTION_CHOICES` gains `("apply_layout", "\U0001f5c2", "Layout")`; `ACTION_TYPE["apply_layout"] = "trigger"`; `PARAM_KEY["apply_layout"] = None`; `_page_for_action["apply_layout"] = <new page index>`.
  - a param page: a `QComboBox` (`self._layout_combo`) of saved layouts by name (userData = id) + `[새로 저장…]` / `[편집…]` buttons that open `LayoutCaptureDialog` and, on accept, reload the combo and select the returned id.
  - `result_binding()` for `apply_layout` returns `Binding(control, "trigger", "apply_layout", {"layout_id": <combo id or "">}, label=label, icon=icon)`.
  - `_apply_binding()` selects the combo entry matching `binding.params["layout_id"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_action_config_dialog.py — add
def test_apply_layout_binding_round_trips(monkeypatch):
    from mpk_deck.core.layout_store import Layout
    import mpk_deck.ui.action_config_dialog as acd

    monkeypatch.setattr(acd, "load_layouts", lambda: {"coding": Layout(name="코딩", items=[])})
    from mpk_deck.core.action_registry import Binding

    existing = Binding("pad_1", "trigger", "apply_layout", {"layout_id": "coding"})
    dialog = acd.ActionConfigDialog("pad_1", existing)
    assert dialog._current_action() == "apply_layout"
    assert dialog.result_binding().params == {"layout_id": "coding"}


def test_apply_layout_with_no_layouts_yields_empty_id(monkeypatch):
    import mpk_deck.ui.action_config_dialog as acd

    monkeypatch.setattr(acd, "load_layouts", lambda: {})
    dialog = acd.ActionConfigDialog("pad_1")
    dialog._select_action("apply_layout")
    assert dialog.result_binding().params == {"layout_id": ""}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ui/test_action_config_dialog.py -q`
Expected: FAIL — `apply_layout` not selectable / not in `_page_for_action`.

- [ ] **Step 3: Write minimal implementation**

- Add `from mpk_deck.core.layout_store import load_layouts` and `from mpk_deck.ui.layout_capture_dialog import LayoutCaptureDialog` to the imports.
- Extend `ACTION_CHOICES`, `ACTION_TYPE`, `PARAM_KEY` as above.
- In `_build_param_stack`, after the sensitivity page, add `self._layout_page = self._add_layout_page()` and `self._page_for_action["apply_layout"] = <its index>` (count the `addWidget` calls; it is index 6).
- `_add_layout_page`:

```python
def _add_layout_page(self):
    page, layout = self._page_shell("레이아웃")
    self._layout_combo = QComboBox()
    self._reload_layout_combo()
    row = QHBoxLayout()
    save_new = QPushButton("새로 저장…"); save_new.setObjectName("ghost")
    edit = QPushButton("편집…"); edit.setObjectName("ghost")
    save_new.clicked.connect(lambda: self._open_capture(None))
    edit.clicked.connect(lambda: self._open_capture(self._layout_combo.currentData()))
    row.addWidget(self._layout_combo, stretch=1)
    row.addWidget(save_new)
    row.addWidget(edit)
    layout.addLayout(row)
    hint = QLabel("저장된 레이아웃을 고르거나 현재 창 배치를 새로 저장하세요.")
    hint.setObjectName("hint"); hint.setWordWrap(True)
    layout.addWidget(hint)
    layout.addStretch(1)
    self._param_stack.addWidget(page)
    return page

def _reload_layout_combo(self):
    current = self._layout_combo.currentData() if hasattr(self, "_layout_combo") else None
    self._layout_combo.clear()
    for lid, lo in load_layouts().items():
        self._layout_combo.addItem(lo.name, lid)
    if current is not None:
        i = self._layout_combo.findData(current)
        if i >= 0:
            self._layout_combo.setCurrentIndex(i)

def _open_capture(self, existing_id):
    dlg = LayoutCaptureDialog(existing_id, accent_hex=self._accent_hex, parent=self)
    if dlg.exec() and dlg.result_layout_id():
        self._reload_layout_combo()
        i = self._layout_combo.findData(dlg.result_layout_id())
        if i >= 0:
            self._layout_combo.setCurrentIndex(i)
```

- `result_binding()` — add a branch before the generic one:

```python
if action == "apply_layout":
    lid = self._layout_combo.currentData() or ""
    return Binding(control=self._control, type="trigger", action="apply_layout",
                   params={"layout_id": lid}, label=label, icon=icon)
```

- `_apply_binding()` — add:

```python
if binding.action == "apply_layout":
    i = self._layout_combo.findData(binding.params.get("layout_id", ""))
    if i >= 0:
        self._layout_combo.setCurrentIndex(i)
    return
```

- Import `QComboBox` from `PySide6.QtWidgets`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q`
Expected: full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py tests/ui/test_action_config_dialog.py
git commit -m "feat(ui): 'Layout' action in the config dialog (pick / save via LayoutCaptureDialog)"
```

---

### Task 5: reload the deck's layout labels after a save

**Files:**
- Modify: `src/mpk_deck/ui/main_window.py`
- Test: covered by Task 2's test + manual

**Interfaces:**
- Consumes: `MainWindow._reload_layouts` (Task 2).
- Produces: after `_on_control_configure_requested` saves an `apply_layout` binding (or any binding — cheap), `MainWindow` calls `self._reload_layouts()` so a freshly-saved layout's name shows on the pad immediately.

- [ ] **Step 1: Add the call**

In `_sync_after_binding_change` (already runs after every binding save), append:

```python
        self._reload_layouts()
```

(This replaces the two `update_bindings` lines added in Task 2's `_sync_after_binding_change` edit if they were added there — `_reload_layouts` already does both. Keep it DRY: `_sync_after_binding_change` calls `_reload_layouts()` instead of the two `update_bindings` calls.)

- [ ] **Step 2: Run the suite**

Run: `python -m pytest -q`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add src/mpk_deck/ui/main_window.py
git commit -m "feat(ui): refresh layout labels on the deck after a binding save"
```

---

### Task 6: `CONTEXT.md` update

**Files:**
- Modify: `mpk-deck/CONTEXT.md`

- [ ] **Step 1: Document**

Add a bullet to the architecture section:

- `core/layout_store.py` + `core/window_layout.py` + `core/browser_url.py` +
  `apply_layout` handler: Workspace Layouts. A layout (`%APPDATA%\mpk-deck\
  layouts.yaml`, `config.LAYOUTS_PATH`) is a named list of items
  (`kind: program|url`, geometry, `maximized`, `title_match`). The `apply_layout`
  trigger loads the layout and runs `restore_layout` on a daemon thread —
  matches already-open windows (repositions, no duplicate), launches the rest
  and polls for their window, then `position_window` (clamped to a visible
  monitor, placed twice to survive a browser's post-show relayout). Browser
  URLs are captured best-effort via UIA (`browser_url.active_tab_url`) with a
  manual URL field in `ui/layout_capture_dialog.py`. Config dialog: the
  "레이아웃" action.
- Note the still-pending move of `actions.yaml` + `QSettings` under
  `config.user_data_dir()` (own task).

- [ ] **Step 2: Commit**

```bash
git add mpk-deck/CONTEXT.md
git commit -m "docs: CONTEXT.md - Workspace Layouts"
```

---

## Self-Review

**Spec coverage:**
- §5.3 `apply_layout` in `ACTION_CHOICES`/`ACTION_TYPE`/`PARAM_KEY`, `action_label` layout resolution, thread `layouts` through views + MainWindow → Tasks 1, 2, 4 ✓
- §8.1 param page (dropdown + 새로 저장/편집) → Task 4 ✓
- §8.2 `LayoutCaptureDialog` → Task 3 ✓
- §8.3 `nl_action` → **Core plan** Task 8 (not here) ✓
- §14 file list: `layout_capture_dialog.py` (Task 3), `action_icons.py` (Task 1), `action_config_dialog.py` (Task 4), `mini_view`/`expanded_view`/`main_window` (Task 2), `CONTEXT.md` (Task 6) ✓

**Placeholder scan:** Task 3's note about `LAYOUTS_PATH` monkeypatch target is a real consistency instruction, not deferred work. Task 4 "index is 6" — the implementer must count the `addWidget` calls; concrete. No TBD/TODO.

**Type consistency:** `action_label(binding, bank_names=None, layouts=None)` — Task 1 defines it, Task 2 calls it with the 3rd positional arg. `update_bindings(bindings, bank_names=None, layouts=None)` — Task 2 both views + MainWindow, matches. `LayoutCaptureDialog(existing_id, accent_hex, dark, parent, *, window_lister, url_reader)` / `.result_layout_id()` — Task 3 defines, Task 4 uses `LayoutCaptureDialog(existing_id, accent_hex=, parent=)` + `.result_layout_id()` ✓. `_reload_layouts` — Task 2 defines, Task 5 uses ✓.

**Gaps:** none. `nl_action` is correctly in the Core plan. This plan is independently testable once the Core plan has landed.
