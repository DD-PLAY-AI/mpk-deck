"""LLM model, effort, chain and system prompt per call, read from ai-hub/llm-registry.toml.

Byte-identical copies live in content-system, trading-system and mpk-deck (repos never
import each other); `ai-hub/scripts/llm-check.py --audit` fails when they drift.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
DEFAULT_REGISTRY = Path(r"C:\DC\DD\ai-hub\llm-registry.toml")
DEFAULT_LOG_DIR = Path(r"C:\DC\DD\llm-calls")
PROVIDER_FIELDS = {
    "claude": {"effort"}, "codex": {"effort"}, "codex_image": {"effort"},
    "gemini": {"thinking_budget"}, "anthropic_api": {"max_tokens"},
}
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
_channel: contextvars.ContextVar[str] = contextvars.ContextVar("llm_channel", default="")


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Step:
    provider: str
    model: str
    effort: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Call:
    id: str
    purpose: str
    chain: tuple[Step, ...]
    attempts_first: int
    system_prompt: str
    templates: tuple[str, ...]


_state: dict = {}


def _reset() -> None:
    _state.clear()


def registry_path() -> Path:
    return Path(os.environ.get("LLM_REGISTRY") or DEFAULT_REGISTRY)


def log_dir() -> Path:
    return Path(os.environ.get("LLM_CALL_LOG_DIR") or DEFAULT_LOG_DIR)


@contextlib.contextmanager
def channel(name: str):
    # Restore the previous value rather than reset(token): a generator holding this open may be
    # closed later from another context, where reset() raises.
    previous = _channel.get()
    _channel.set(name)
    try:
        yield
    finally:
        _channel.set(previous)


def _stamp(path: Path) -> tuple:
    prompts = path.parent / "prompts"
    files = [path, *sorted(prompts.glob("*.txt"))] if prompts.is_dir() else [path]
    return tuple((str(f), f.stat().st_mtime_ns) for f in files)


def _step(i: int, spec: dict) -> Step:
    spec = dict(spec)
    provider, model = spec.pop("provider", None), spec.pop("model", "")
    if provider not in PROVIDER_FIELDS:
        raise RegistryError(f"chain[{i}] unknown provider {provider!r}")
    if not model:
        raise RegistryError(f"chain[{i}] model missing")
    unknown = set(spec) - PROVIDER_FIELDS[provider]
    if unknown:
        raise RegistryError(f"chain[{i}] {provider} does not take {sorted(unknown)}")
    effort = spec.pop("effort", None)
    if effort is not None and (effort not in EFFORTS or "haiku" in model):
        raise RegistryError(f"chain[{i}] effort {effort!r} not valid for {model}")
    return Step(provider, model, effort, spec)


def _call(call_id: str, spec: dict, base: Path) -> Call:
    chain = tuple(_step(i, s) for i, s in enumerate(spec.get("chain") or []))
    if not chain:
        raise RegistryError("empty chain")
    text = ""
    if spec.get("system_prompt"):
        prompt = base / spec["system_prompt"]
        if not prompt.is_file():
            raise RegistryError(f"system_prompt {spec['system_prompt']} not found")
        text = prompt.read_text(encoding="utf-8")
    return Call(call_id, spec.get("purpose", ""), chain, int(spec.get("attempts_first", 1)),
                text, tuple(spec.get("templates", [])))


def parse(path: Path) -> tuple[dict[str, Call], dict[str, tuple[float, float]]]:
    """Parse and validate the whole file; raises RegistryError listing every problem."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise RegistryError(f"{path}: {e}") from e
    if raw.get("schema") != 1:
        raise RegistryError("schema must be 1")
    calls, errors = {}, []
    for call_id, spec in raw.get("calls", {}).items():
        try:
            calls[call_id] = _call(call_id, spec, path.parent)
        except RegistryError as e:
            errors.append(f"{call_id}: {e}")
    if errors:
        raise RegistryError("; ".join(errors))
    pricing = {m: (float(p["input"]), float(p["output"])) for m, p in raw.get("pricing", {}).items()}
    return calls, pricing


def _load() -> tuple[dict[str, Call], dict[str, tuple[float, float]]]:
    path = registry_path()
    try:
        stamp = _stamp(path)
    except OSError as e:
        stamp, error = None, RegistryError(f"{path}: {e}")
    else:
        if _state.get("stamp") == stamp:
            return _state["calls"], _state["pricing"]
        try:
            _state["calls"], _state["pricing"] = parse(path)
            _state["stamp"] = stamp
            (log_dir() / "registry-error.json").unlink(missing_ok=True)
            return _state["calls"], _state["pricing"]
        except RegistryError as e:
            error = e
    if "calls" not in _state:
        raise error
    log.error("llm registry invalid, keeping last good version: %s", error)
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        (log_dir() / "registry-error.json").write_text(json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "error": str(error)}, ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        log.exception("could not write registry-error.json")
    return _state["calls"], _state["pricing"]


def resolve(call_id: str) -> Call:
    calls, _ = _load()
    if call_id not in calls:
        raise KeyError(f"{call_id} not in {registry_path()} -- register new LLM calls there first")
    return calls[call_id]


def price(model: str) -> tuple[float, float] | None:
    return _load()[1].get(model)


def pricing_table() -> dict[str, dict[str, float]]:
    return {m: {"input": i, "output": o} for m, (i, o) in _load()[1].items()}


def log_call(call_id: str, step: Step, *, attempt: int, elapsed_s: float, ok: bool,
             tokens_in: int | None = None, tokens_out: int | None = None,
             usd: float | None = None, error: str | None = None) -> None:
    """Append one attempt to llm-calls/<system>-YYYY-MM.jsonl. Never raises."""
    source = "provider" if usd is not None else None
    rate = price(step.model) if usd is None and tokens_in is not None else None
    if rate:
        usd = round((tokens_in * rate[0] + (tokens_out or 0) * rate[1]) / 1_000_000, 6)
        source = "price"
    now = datetime.now(timezone.utc)
    system = call_id.split(".", 1)[0]
    line = {"ts": now.isoformat(), "system": system, "channel": _channel.get(), "id": call_id,
            "attempt": attempt, "provider": step.provider, "model": step.model, "effort": step.effort,
            "elapsed_s": round(elapsed_s, 2), "tokens_in": tokens_in, "tokens_out": tokens_out,
            "usd": usd, "usd_source": source, "ok": ok, "error": (error or None) and error[:300]}
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        with open(log_dir() / f"{system}-{now:%Y-%m}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")   # one write per line
    except OSError:
        log.exception("llm call log write failed")
