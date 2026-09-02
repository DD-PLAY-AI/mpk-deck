import logging
import os
import re
import tempfile
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
    label: str = ""  # user-set name shown on the deck; "" = auto (see ui/action_icons.action_label)
    icon: str = ""  # custom icon SVG body ({accent}/{neutral} slots); "" = auto (app icon / built-in glyph)


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


DEFAULT_JOYSTICK_SENSITIVITY = 1.0


def default_joystick_bindings() -> list[Binding]:
    """Every bank should scroll out of the box - see docs/superpowers/specs/
    2026-08-28-joystick-scroll-design.md. Returns a fresh list every call; Binding
    is frozen but the containing list must never be shared/mutated across banks."""
    return [
        Binding(
            control="joystick_x",
            type="continuous",
            action="scroll_horizontal",
            params={"sensitivity": DEFAULT_JOYSTICK_SENSITIVITY},
        ),
        Binding(
            control="joystick_y",
            type="continuous",
            action="scroll_vertical",
            params={"sensitivity": DEFAULT_JOYSTICK_SENSITIVITY},
        ),
    ]


def _backfill_joystick_bindings(bindings: list[Binding]) -> list[Binding]:
    controls = {b.control for b in bindings}
    return bindings + [b for b in default_joystick_bindings() if b.control not in controls]


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
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())},
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

    if not isinstance(data, dict):
        logger.warning("%s did not contain a mapping at the top level, starting with defaults", path)
        return _default_config()

    if "banks" in data:
        try:
            return _parse_new_format(data)
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning("failed to parse bank data in %s (%s), starting with defaults", path, exc)
            return _default_config()

    # old flat format (or an empty/near-empty file) -> migrate
    raw_bindings = data.get("bindings", []) or []
    bindings = _backfill_joystick_bindings(_parse_bindings_list(raw_bindings))
    return DeckConfig(
        active_bank=DEFAULT_BANK_ID,
        switch_bindings={DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID},
        banks={DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=bindings)},
    )


def _parse_new_format(data: dict) -> DeckConfig:
    banks = {}
    for bank_id, bank_data in (data.get("banks") or {}).items():
        raw_bindings = bank_data.get("bindings", []) or []
        bindings = _backfill_joystick_bindings(_parse_bindings_list(raw_bindings))
        banks[bank_id] = Bank(name=bank_data.get("name", bank_id), bindings=bindings)
    if not banks:
        banks = {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}
    switch_bindings = dict(data.get("switch_bindings") or {})
    active_bank = data.get("active_bank") or DEFAULT_BANK_ID
    if active_bank not in banks:
        active_bank = next(iter(banks))
    return DeckConfig(active_bank=active_bank, switch_bindings=switch_bindings, banks=banks)


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
    for bank in data["banks"].values():
        for bd in bank["bindings"]:
            for optional in ("label", "icon"):
                if not bd.get(optional):
                    bd.pop(optional, None)  # keep the file clean - "" is the default
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # keep Korean labels readable
    # Atomic write: a crash mid-write must not truncate an existing config -
    # load_config falls back to defaults on a broken file, which silently drops
    # every binding. Write a sibling temp file, fsync, then os.replace (atomic
    # on the same filesystem).
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


def _parse_binding(entry: dict) -> Binding:
    control = entry["control"]
    btype = entry["type"]
    if btype not in ("trigger", "continuous"):
        raise ValueError(f"unknown binding type: {btype!r}")
    action = entry["action"]
    params = entry.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be a mapping")
    label = entry.get("label") or ""
    icon = entry.get("icon") or ""
    return Binding(control=control, type=btype, action=action, params=params, label=str(label), icon=str(icon))
