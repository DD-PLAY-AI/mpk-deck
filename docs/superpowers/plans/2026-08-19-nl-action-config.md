# Natural-Language Action Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user type a plain-language description into `ActionConfigDialog` (e.g. "카카오톡 열어줘") and have Claude Haiku 4.5 propose a `Binding` that fills the existing action/param fields for review — the user still clicks Save.

**Architecture:** A new `core/nl_action.py` module calls the Anthropic Messages API with a single forced tool (`propose_binding`) so the response is always structured. `launch_program` proposals are grounded against the real installed-program list (`program_finder.list_installed_programs()`) — a name the model invents that isn't in that list is rejected, never trusted as a path. `ActionConfigDialog` gets one new input + button that calls this function and reuses the exact same "populate fields from a `Binding`" code path `existing` bindings already use on dialog open.

**Tech Stack:** `anthropic` (Python SDK) for the API call, `python-dotenv` to load `ANTHROPIC_API_KEY` from a gitignored `.env` file. No new UI framework — same PySide6 widgets as the rest of the dialog.

**Spec:** `docs/superpowers/specs/2026-08-19-nl-action-config-design.md`

## Global Constraints

- `ANTHROPIC_API_KEY` comes from `.env` (already gitignored) via `python-dotenv`, loaded once at app startup in `__main__.py`. No in-app key-entry UI.
- The LLM never executes anything — it only ever proposes a `Binding` that flows through the exact same `action_registry` validation and `save_bindings()` path a manual dialog edit already uses. The user must click Save.
- `launch_program` proposals are only ever accepted if the model's chosen program name exactly matches one from the real installed-program list — never a model-invented path.
- Model: `claude-haiku-4-5` (cheap, sufficient for this short structured-extraction task — do not use a larger model here).
- `client` is injectable on `parse_nl_action` (same pattern as `handlers.py`'s `finder`/`volume_setter` and `program_finder.py`'s `resolver`) so tests never make a real network call.
- Any failure (missing key, network error, ambiguous/invalid model output) returns `None` from `parse_nl_action` — never raises out into the UI.
- No git worktree for this work — commit and push directly on `main` (solo project, user's explicit instruction).

---

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `anthropic` and `python-dotenv` importable in the installed environment.

- [ ] **Step 1: Add the two dependencies**

In `pyproject.toml`, add to the `dependencies` list (alongside `PySide6`, `mido`, etc.):

```toml
    "anthropic>=0.40",
    "python-dotenv>=1.0",
```

- [ ] **Step 2: Reinstall and verify**

Run: `pip install -e ".[dev]"`
Run: `python -c "import anthropic, dotenv; print('ok')"`
Expected: prints `ok` with no error.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add anthropic and python-dotenv dependencies"
git push
```

---

### Task 2: `core/nl_action.py` — propose a Binding from plain text

**Files:**
- Create: `src/mpk_deck/core/nl_action.py`
- Test: `tests/core/test_nl_action.py`

**Interfaces:**
- Consumes: `Binding` (`mpk_deck.core.action_registry`), `InstalledProgram` (`mpk_deck.core.program_finder`).
- Produces: `parse_nl_action(text: str, installed_programs: list[InstalledProgram], *, client=None) -> Binding | None`. The returned `Binding.control` is always `""` — the caller (Task 4) ignores it and only reads `.action`/`.params`; only the caller knows which control is being configured.

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_nl_action.py
from types import SimpleNamespace

from mpk_deck.core.nl_action import parse_nl_action
from mpk_deck.core.program_finder import InstalledProgram

PROGRAMS = [
    InstalledProgram(name="KakaoTalk", path="C:/Program Files (x86)/Kakao/KakaoTalk/KakaoTalk.exe"),
    InstalledProgram(name="Chrome", path="C:/Program Files/Google/Chrome/Application/chrome.exe"),
]


class FakeMessages:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._exc:
            raise self._exc
        return self._response


class FakeClient:
    def __init__(self, response=None, exc=None):
        self.messages = FakeMessages(response, exc)


def _tool_use_response(input_dict):
    block = SimpleNamespace(type="tool_use", name="propose_binding", input=input_dict)
    return SimpleNamespace(content=[block])


def test_launch_program_matches_installed_program():
    client = FakeClient(_tool_use_response({"action": "launch_program", "program_name": "KakaoTalk"}))

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS, client=client)

    assert result.action == "launch_program"
    assert result.type == "trigger"
    assert result.params == {"path": "C:/Program Files (x86)/Kakao/KakaoTalk/KakaoTalk.exe"}


def test_launch_program_rejects_program_not_in_installed_list():
    client = FakeClient(_tool_use_response({"action": "launch_program", "program_name": "Some Fake App"}))

    result = parse_nl_action("가짜 앱 열어줘", PROGRAMS, client=client)

    assert result is None


def test_open_url_adds_https_scheme_when_missing():
    client = FakeClient(_tool_use_response({"action": "open_url", "url": "youtube.com"}))

    result = parse_nl_action("유튜브 열어줘", PROGRAMS, client=client)

    assert result.action == "open_url"
    assert result.params == {"url": "https://youtube.com"}


def test_focus_window_passes_through_title():
    client = FakeClient(_tool_use_response({"action": "focus_window", "title_contains": "Notepad"}))

    result = parse_nl_action("메모장 찾아줘", PROGRAMS, client=client)

    assert result.params == {"title_contains": "Notepad"}


def test_set_system_volume_has_no_params():
    client = FakeClient(_tool_use_response({"action": "set_system_volume"}))

    result = parse_nl_action("볼륨 조절", PROGRAMS, client=client)

    assert result.action == "set_system_volume"
    assert result.type == "continuous"
    assert result.params == {}


def test_unknown_action_name_returns_none():
    client = FakeClient(_tool_use_response({"action": "delete_all_files"}))

    result = parse_nl_action("...", PROGRAMS, client=client)

    assert result is None


def test_api_error_returns_none():
    client = FakeClient(exc=RuntimeError("network down"))

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS, client=client)

    assert result is None


def test_empty_text_returns_none_without_calling_client():
    client = FakeClient()

    result = parse_nl_action("   ", PROGRAMS, client=client)

    assert result is None
    assert client.messages.last_kwargs is None


def test_missing_api_key_returns_none_without_calling_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS)

    assert result is None


def test_call_uses_haiku_model_and_forces_the_tool():
    client = FakeClient(_tool_use_response({"action": "open_url", "url": "https://example.com"}))

    parse_nl_action("open example.com", PROGRAMS, client=client)

    kwargs = client.messages.last_kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["tool_choice"] == {
        "type": "tool",
        "name": "propose_binding",
        "disable_parallel_tool_use": True,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_nl_action.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mpk_deck.core.nl_action'`

- [ ] **Step 3: Write the implementation**

```python
# src/mpk_deck/core/nl_action.py
import logging
import os
from typing import Optional

import anthropic

from mpk_deck.core.action_registry import Binding
from mpk_deck.core.program_finder import InstalledProgram

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
}

_TOOL = {
    "name": "propose_binding",
    "description": (
        "Propose one mpk-deck action binding for the user's plain-language request. "
        "`program_name` (for launch_program) must exactly match one of the provided "
        "installed program names -- never invent a path or program that isn't listed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(ACTION_TYPE.keys()),
            },
            "program_name": {
                "type": "string",
                "description": "Required for launch_program; must exactly match a name from the installed program list.",
            },
            "url": {"type": "string", "description": "Required for open_url."},
            "title_contains": {"type": "string", "description": "Required for focus_window."},
        },
        "required": ["action"],
    },
}


def parse_nl_action(
    text: str,
    installed_programs: list[InstalledProgram],
    *,
    client: Optional["anthropic.Anthropic"] = None,
) -> Binding | None:
    if not text.strip():
        return None

    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("parse_nl_action: ANTHROPIC_API_KEY not set")
            return None
        client = anthropic.Anthropic(api_key=api_key)

    program_names = ", ".join(p.name for p in installed_programs) or "(none found)"
    prompt = f"User request: {text}\n\nInstalled programs (for launch_program only): {program_names}"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "propose_binding", "disable_parallel_tool_use": True},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.exception("parse_nl_action: API call failed")
        return None

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        return None

    return _to_binding(tool_block.input, installed_programs)


def _to_binding(data: dict, installed_programs: list[InstalledProgram]) -> Binding | None:
    action = data.get("action")
    if action not in ACTION_TYPE:
        return None

    if action == "launch_program":
        name = data.get("program_name", "")
        match = next((p for p in installed_programs if p.name == name), None)
        if match is None:
            return None
        params = {"path": match.path}
    elif action == "open_url":
        url = (data.get("url") or "").strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        params = {"url": url}
    elif action == "focus_window":
        title = (data.get("title_contains") or "").strip()
        if not title:
            return None
        params = {"title_contains": title}
    else:  # set_system_volume
        params = {}

    return Binding(control="", type=ACTION_TYPE[action], action=action, params=params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_nl_action.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/mpk_deck/core/nl_action.py tests/core/test_nl_action.py
git commit -m "feat: add parse_nl_action for LLM-proposed Bindings"
git push
```

---

### Task 3: Load `.env` at app startup

**Files:**
- Modify: `src/mpk_deck/__main__.py`

**Interfaces:**
- Consumes: `python-dotenv`'s `load_dotenv()`.
- Produces: `ANTHROPIC_API_KEY` (if present in `.env`) available via `os.environ` before `MainWindow` (and therefore any `ActionConfigDialog`) is constructed.

- [ ] **Step 1: Add the load_dotenv() call**

```python
# src/mpk_deck/__main__.py
import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from mpk_deck.ui.main_window import MainWindow


def main() -> None:
    load_dotenv()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(680, 420)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manually verify**

Create `C:\DC\DD\mpk-deck\.env` (already gitignored) with a line `ANTHROPIC_API_KEY=sk-ant-...` (a real key), then:

Run: `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.environ.get('ANTHROPIC_API_KEY')))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add src/mpk_deck/__main__.py
git commit -m "feat: load .env at startup for ANTHROPIC_API_KEY"
git push
```

---

### Task 4: Wire the NL input into `ActionConfigDialog`

**Files:**
- Modify: `src/mpk_deck/ui/action_config_dialog.py`

**Interfaces:**
- Consumes: `parse_nl_action` (Task 2), `list_installed_programs` (already imported in this file).
- Produces: no new public interface — this is the dialog's own UI wiring, manually verified (no pytest coverage for this file, consistent with the rest of the dialog).

- [ ] **Step 1: Add the import**

Add to the top of `src/mpk_deck/ui/action_config_dialog.py`:

```python
from mpk_deck.core.nl_action import parse_nl_action
```

- [ ] **Step 2: Add the `nlError` QSS rule**

In `DIALOG_QSS`, add this rule (anywhere among the other rules, e.g. right after the `QLabel#heading` rule):

```python
QLabel#nlError {{ color: #ff6b6b; font-size: 11px; }}
```

- [ ] **Step 3: Extract `_apply_binding` and use it for `existing`**

Replace this block near the end of `__init__`:

```python
        self._select_action(existing.action if existing else ACTION_CHOICES[0][0])
        if existing is not None:
            key = PARAM_KEY.get(existing.action)
            if key:
                self._param_edit_for(existing.action).setText(str(existing.params.get(key, "")))
```

with:

```python
        if existing is not None:
            self._apply_binding(existing)
        else:
            self._select_action(ACTION_CHOICES[0][0])
```

Add the new method anywhere among the other methods (e.g. right after `_select_action`):

```python
    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))
```

- [ ] **Step 4: Add the NL input row above the action list/param body**

In `__init__`, right before the `body = QHBoxLayout()` line, add:

```python
        self._nl_edit = QLineEdit(self)
        self._nl_edit.setPlaceholderText("or describe what you want...")
        self._nl_generate_btn = QPushButton("Generate", self)
        self._nl_generate_btn.clicked.connect(self._on_generate_clicked)
        self._nl_error = QLabel("", self)
        self._nl_error.setObjectName("nlError")

        nl_row = QHBoxLayout()
        nl_row.addWidget(self._nl_edit, stretch=1)
        nl_row.addWidget(self._nl_generate_btn)
```

Then, in the `root = QVBoxLayout(self)` block below, add the new row and error label between `heading` and `body`:

```python
        root.addWidget(heading)
        root.addLayout(nl_row)
        root.addWidget(self._nl_error)
        root.addLayout(body, stretch=1)
```

(This replaces the existing `root.addWidget(heading)` / `root.addLayout(body, stretch=1)` pair — keep `root.addWidget(buttons)` as the last line, unchanged.)

- [ ] **Step 5: Add the click handler**

Add this method (e.g. after `_apply_binding`):

```python
    def _on_generate_clicked(self) -> None:
        text = self._nl_edit.text()
        self._nl_error.setText("")
        self._nl_generate_btn.setEnabled(False)
        self._nl_generate_btn.repaint()
        try:
            binding = parse_nl_action(text, list_installed_programs())
        finally:
            self._nl_generate_btn.setEnabled(True)

        if binding is None:
            self._nl_error.setText("Couldn't figure that out - try rephrasing, or check ANTHROPIC_API_KEY in .env")
            return
        self._apply_binding(binding)
```

- [ ] **Step 6: Run the full suite to confirm nothing broke**

Run: `pytest -v`
Expected: all tests still pass (this task adds no new tests — the dialog has no pytest coverage by project convention).

- [ ] **Step 7: Manually verify**

With a real `ANTHROPIC_API_KEY` in `.env`, run: `python -m mpk_deck`

Double-click a pad to open `ActionConfigDialog`. Type "카카오톡 열어줘" (or any installed program's purpose) into the new field and click Generate. Expected: the action list selects `Launch Program` and the program-path field fills in with a real installed program's path, no error shown. Try an ambiguous/nonsense phrase (e.g. "asdkfj"); expected: the red error label appears, existing fields untouched. Click Save on a successful proposal; expected: `config/actions.yaml` gets the new binding (same as a manual edit would produce).

- [ ] **Step 8: Commit**

```bash
git add src/mpk_deck/ui/action_config_dialog.py
git commit -m "feat: add natural-language action proposal to ActionConfigDialog"
git push
```

---

### Task 5: Docs

**Files:**
- Modify: `mpk-deck/CLAUDE.md`
- Modify: `mpk-deck/README.md`
- Modify: `C:\DC\DD\ROADMAP.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update `mpk-deck/CLAUDE.md`**

Remove/replace the now-stale line "No AI/LLM calls anywhere in this repo — natural-language action editing belongs in ai-hub, not here" with a short note that `core/nl_action.py` is the one deliberate, scoped exception (Claude Haiku, tool-forced structured output only, never auto-executes, `ANTHROPIC_API_KEY` via `.env`) — link to the 2026-08-19 spec.

- [ ] **Step 2: Update `mpk-deck/README.md`**

Mention the natural-language action config in the feature list, and note the `.env` + `ANTHROPIC_API_KEY` requirement for that one feature (everything else in the app works with zero API keys / network access).

- [ ] **Step 3: Update `C:\DC\DD\ROADMAP.md`**

Check off the relevant item / add a line under `mpk-deck`'s roadmap section noting the natural-language action config feature landed, plus a Decision Log entry dated 2026-08-19 noting the deliberate scoped exception to the "no AI calls in mpk-deck" original design.

- [ ] **Step 4: Commit**

```bash
git add "C:\DC\DD\mpk-deck\CLAUDE.md" "C:\DC\DD\mpk-deck\README.md" "C:\DC\DD\ROADMAP.md"
git commit -m "docs: document natural-language action config feature"
git push
```

## Post-Plan Checklist

- [ ] Run the full suite once more: `pytest -v` — all tests (Task 2's new ones plus the existing 48) should pass.
- [ ] Confirm `.env` is not tracked by git: `git status` should never show it; `git check-ignore -v .env` should print a match.
- [ ] Confirm `git log --oneline -1 -- .env` returns nothing (it was never committed).
