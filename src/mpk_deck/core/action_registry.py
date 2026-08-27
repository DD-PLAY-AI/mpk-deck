import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

import yaml

logger = logging.getLogger(__name__)

BindingType = Literal["trigger", "continuous"]


@dataclass(frozen=True)
class Binding:
    control: str
    type: BindingType
    action: str
    params: dict = field(default_factory=dict)


DEFAULT_BANK_ID = "bank_a"
DEFAULT_BANK_NAME = "Home"
DEFAULT_SWITCH_CONTROL = "key_0"


@dataclass
class Bank:
    name: str
    bindings: list[Binding] = field(default_factory=list)


@dataclass
class DeckConfig:
    active_bank: str
    switch_bindings: dict[str, str]
    banks: dict[str, Bank]


def generate_bank_id(name: str, existing_ids: Iterable[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "bank"
    existing = set(existing_ids)
    candidate = slug
    n = 2
    while candidate in existing:
        candidate = f"{slug}_{n}"
        n += 1
    return candidate


def _parse_bindings_list(raw_bindings: list) -> list[Binding]:
    bindings: list[Binding] = []
    for i, entry in enumerate(raw_bindings):
        try:
            bindings.append(_parse_binding(entry))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("skipping invalid binding at index %d: %s", i, exc)
    return bindings


def _default_config() -> DeckConfig:
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])},
    )


def load_config(path: str | Path) -> DeckConfig:
    path = Path(path)
    if not path.exists():
        return _default_config()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        logger.warning("failed to parse %s, starting with defaults", path)
        return _default_config()

    if "banks" in data:
        banks = {}
        for bank_id, bank_data in (data.get("banks") or {}).items():
            raw_bindings = bank_data.get("bindings", []) or []
            banks[bank_id] = Bank(name=bank_data.get("name", bank_id), bindings=_parse_bindings_list(raw_bindings))
        return DeckConfig(
            active_bank=data.get("active_bank") or DEFAULT_BANK_ID,
            switch_bindings=dict(data.get("switch_bindings") or {}),
            banks=banks,
        )

    # old flat format (or an empty/near-empty file) -> migrate
    raw_bindings = data.get("bindings", []) or []
    bindings = _parse_bindings_list(raw_bindings)
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=bindings)},
    )


def save_config(path: str | Path, config: DeckConfig) -> None:
    path = Path(path)
    data = {
        "active_bank": config.active_bank,
        "switch_bindings": config.switch_bindings,
        "banks": {
            bank_id: {"name": bank.name, "bindings": [asdict(b) for b in bank.bindings]}
            for bank_id, bank in config.banks.items()
        },
    }
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
