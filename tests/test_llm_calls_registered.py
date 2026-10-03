"""Every LLM call goes through ai-hub/llm-registry.toml (T-0106).

A direct SDK call or a model id written in code fails here -- register the call in the registry
and read it through `mpk_deck.core.llm_registry`.
"""
import re
from pathlib import Path

import pytest

from mpk_deck.core import llm_registry

SRC = Path(__file__).resolve().parents[1] / "src" / "mpk_deck"
REAL_REGISTRY = Path(r"C:\DC\DD\ai-hub\llm-registry.toml")
DIRECT = re.compile(r'"claude",\s*"-p"|"exec",\s*"--json"|messages\.create\(|genai\.Client\(|'
                    r'generativelanguage|["\'](claude-[a-z0-9-]+|gpt-[0-9][\w.-]*|gemini-[0-9][\w.-]*)["\']')
CALL_SITES = {"llm_registry.py", "icon_gen.py", "nl_action.py"}  # may call the SDK, never name a model
IDS = re.compile(r'["\'](mpk\.[a-z_]+)["\']')


def test_no_direct_call_or_model_literal_outside_call_sites():
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = DIRECT.search(line)
            if m and (path.name not in CALL_SITES or m.group(1)):
                hits.append(f"{path.relative_to(SRC)}:{n}: {line.strip()}")
    assert not hits, "register the call in ai-hub/llm-registry.toml and read it via llm_registry:\n" + "\n".join(hits)


def test_every_call_id_is_registered():
    if not REAL_REGISTRY.exists():
        pytest.skip("ai-hub/llm-registry.toml not on this machine")
    ids = set()
    for path in SRC.rglob("*.py"):
        ids |= set(IDS.findall(path.read_text(encoding="utf-8")))
    assert ids and not sorted(ids - set(llm_registry.parse(REAL_REGISTRY)[0]))


def test_missing_registry_turns_the_llm_feature_off(monkeypatch, tmp_path):
    from mpk_deck.core import icon_gen

    monkeypatch.setenv("LLM_REGISTRY", str(tmp_path / "absent.toml"))
    llm_registry._reset()
    assert icon_gen.generate_icon_svg("play", client=object()) is None
