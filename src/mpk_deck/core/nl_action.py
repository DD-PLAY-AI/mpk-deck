import logging
import os
from typing import Optional

import anthropic

from mpk_deck.core.action_registry import Binding
from mpk_deck.core.layout_store import load_layouts
from mpk_deck.core.program_finder import InstalledProgram

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
    "apply_layout": "trigger",
    "set_display_brightness": "continuous",
    "run_shell_command": "trigger",
    "media_key": "trigger",
}

_TOOL = {
    "name": "propose_binding",
    "description": (
        "Propose one mpk-deck action binding for the user's plain-language request. "
        "`program_name` (for launch_program) must exactly match one of the provided "
        "installed program names -- never invent a path or program that isn't listed."
        " run_shell_command's command is run in a shell; media_key is one of play_pause/next/prev/stop."
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
            "layout_name": {"type": "string", "description": "Required for apply_layout; the name of a saved layout."},
            "command": {
                "type": "string",
                "description": "Required for run_shell_command; a shell command line (run with shell=True).",
            },
            "media_key": {
                "type": "string",
                "enum": ["play_pause", "next", "prev", "stop"],
                "description": "Required for media_key; which media transport key to send.",
            },
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
    elif action == "apply_layout":
        name = (data.get("layout_name") or "").strip()
        layouts = load_layouts()
        match = next((lid for lid, lo in layouts.items() if lo.name == name), None)
        if match is None:
            match = next((lid for lid, lo in layouts.items() if lo.name.lower() == name.lower()), None)
        if match is None:
            return None
        params = {"layout_id": match}
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
    else:  # set_system_volume
        params = {}

    return Binding(control="", type=ACTION_TYPE[action], action=action, params=params)
