"""AI-generated icons for a binding, in the deck's line style.

Scoped AI exception, same shape as core/nl_action.py: Claude Haiku, tool-forced
structured output, ANTHROPIC_API_KEY from .env, `client` injectable, returns None
on any failure so the caller degrades to the built-in icon.

Returns an SVG *body* (elements only, no <svg> wrapper) that may contain the
{accent} / {neutral} colour slots - rendered by ui/action_icons.render_svg_icon.
"""

import logging
import os
import xml.etree.ElementTree as ET
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

_SYSTEM = (
    "You draw tiny monochrome-style UI icons for a hardware control-surface app. "
    "Output an SVG body only (child elements, no <svg> wrapper), designed on a "
    "0 0 64 64 viewBox. Rules: use <path>, <rect>, <circle>, <line>, <polyline>, "
    "<polygon> only. Strokes ~5 wide, stroke-linecap=round, stroke-linejoin=round. "
    "Exactly two colours, given as the literal tokens {accent} (the main subject) "
    "and {neutral} (supporting/context shapes). No text, no gradients, no filters, "
    "no <image>, no <use>, no external refs, no scripts. At most 6 elements. "
    "Geometric and legible at 20px."
)

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
# blocks processing instructions. A legit icon body needs none of these.
_FORBIDDEN = (
    "<script", "<image", "<foreignobject", "<use", "xlink", "href",
    "http://", "https://", "data:", "<style", "<!", "<?", "&",
)

_MAX_LEN = 4000


def _looks_safe(svg_body: str) -> bool:
    if len(svg_body) > _MAX_LEN:
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
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=_SYSTEM,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "emit_icon", "disable_parallel_tool_use": True},
            messages=[{"role": "user", "content": f"Icon for: {description}"}],
        )
    except Exception:
        logger.exception("generate_icon_svg: API call failed")
        return None

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        return None
    svg_body = (tool_block.input or {}).get("svg_body", "").strip()
    if not svg_body or not _looks_safe(svg_body):
        logger.warning("generate_icon_svg: model returned unusable SVG")
        return None
    return svg_body
