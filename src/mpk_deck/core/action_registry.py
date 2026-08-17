import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)

BindingType = Literal["trigger", "continuous"]


@dataclass(frozen=True)
class Binding:
    control: str
    type: BindingType
    action: str
    params: dict = field(default_factory=dict)


class ActionConfigError(Exception):
    pass


def load_bindings(path: str | Path) -> list[Binding]:
    path = Path(path)
    if not path.exists():
        raise ActionConfigError(f"actions file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw_bindings = data.get("bindings", []) or []
    bindings: list[Binding] = []
    for i, entry in enumerate(raw_bindings):
        try:
            bindings.append(_parse_binding(entry))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("skipping invalid binding at index %d: %s", i, exc)
    return bindings


def save_bindings(path: str | Path, bindings: list[Binding]) -> None:
    path = Path(path)
    data = {"bindings": [asdict(b) for b in bindings]}
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _parse_binding(entry: dict) -> Binding:
    control = entry["control"]
    btype = entry["type"]
    if btype not in ("trigger", "continuous"):
        raise ValueError(f"unknown binding type: {btype!r}")
    action = entry["action"]
    params = entry.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be a mapping")
    return Binding(control=control, type=btype, action=action, params=params)
