"""AI-generated icons for a binding, in the deck's line style.

Scoped AI exception, same shape as core/nl_action.py: Claude Haiku, tool-forced
structured output, ANTHROPIC_API_KEY from .env, `client` injectable, returns None
on any failure so the caller degrades to the built-in icon.

Returns an SVG *body* (elements only, no <svg> wrapper) that may contain the
{accent} / {neutral} colour slots - rendered by ui/action_icons.render_svg_icon.
"""

import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Optional

import anthropic

from mpk_deck.core import llm_registry

logger = logging.getLogger(__name__)


# The system prompt lives in ai-hub/prompts/mpk.icon_gen.txt (T-0106).

_TOOL = {
    "name": "emit_icon",
    "description": "Return the finished SVG body for the requested icon.",
    "input_schema": {
        "type": "object",
        "properties": {"svg_body": {"type": "string", "description": "SVG child elements, no <svg> wrapper."}},
        "required": ["svg_body"],
    },
}

# "<!" and "&" are rejected before parsing, so DOCTYPE/ENTITY declarations and
# entity references never reach the XML parser - no XXE, no billion-laughs. "<?"
# blocks processing instructions. The rest block external refs (SSRF) and the
# renderer-side DoS surface (<filter>/<animate>/<pattern>/<mask>, nested <svg>,
# url(...) paints). A legit icon body needs none of these.
_FORBIDDEN = (
    "<script", "<image", "<foreignobject", "<use", "xlink", "href",
    "http://", "https://", "data:", "<style", "<!", "<?", "&",
    "<filter", "<animate", "<set", "<pattern", "<mask", "<svg", "url(",
)

_MAX_LEN = 4000


def is_safe_svg_body(svg_body: str) -> bool:
    """Cheap denylist + well-formedness check for an SVG icon body (no <svg>
    wrapper). Run at generation time AND before rendering anything loaded from
    actions.yaml."""
    if not svg_body or len(svg_body) > _MAX_LEN:
        return False
    low = svg_body.lower()
    if any(tok in low for tok in _FORBIDDEN):
        return False
    try:
        ET.fromstring(f"<svg xmlns='http://www.w3.org/2000/svg'>{svg_body}</svg>")
    except ET.ParseError:
        return False
    return True


def generate_icon_svg(description: str, *, client: Optional["anthropic.Anthropic"] = None) -> str | None:
    if not description.strip():
        return None

    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("generate_icon_svg: ANTHROPIC_API_KEY not set")
            return None
        client = anthropic.Anthropic(api_key=api_key)

    try:
        call = llm_registry.resolve("mpk.icon_gen")
    except (llm_registry.RegistryError, KeyError) as exc:
        # mpk-deck runs on its own; without the registry only the LLM feature is off.
        logger.warning("generate_icon_svg: LLM registry unavailable: %s", exc)
        return None
    step = call.chain[0]
    started = time.monotonic()
    try:
        response = client.messages.create(
            model=step.model,
            max_tokens=step.extra.get("max_tokens", 512),
            system=call.system_prompt,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "emit_icon", "disable_parallel_tool_use": True},
            messages=[{"role": "user", "content": f"Icon for: {description}"}],
        )
    except Exception as exc:
        llm_registry.log_call("mpk.icon_gen", step, attempt=1, elapsed_s=time.monotonic() - started, ok=False, error=str(exc))
        logger.exception("generate_icon_svg: API call failed")
        return None
    usage = getattr(response, "usage", None)
    llm_registry.log_call("mpk.icon_gen", step, attempt=1, elapsed_s=time.monotonic() - started, ok=True,
                          tokens_in=getattr(usage, "input_tokens", None), tokens_out=getattr(usage, "output_tokens", None))

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        return None
    svg_body = (tool_block.input or {}).get("svg_body", "").strip()
    if not is_safe_svg_body(svg_body):
        logger.warning("generate_icon_svg: model returned unusable SVG")
        return None
    return svg_body
