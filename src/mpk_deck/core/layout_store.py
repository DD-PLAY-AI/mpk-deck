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
