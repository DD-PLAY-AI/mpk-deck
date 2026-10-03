import shutil
from pathlib import Path

import pytest

REAL_REGISTRY = Path(r"C:\DC\DD\ai-hub\llm-registry.toml")


@pytest.fixture(autouse=True)
def _llm_registry_copy(tmp_path_factory, monkeypatch):
    """Tests run on a private copy of the LLM registry and a temp call log (T-0106)."""
    from mpk_deck.core import llm_registry

    # Outside tmp_path: some tests list tmp_path and expect only their own files.
    root = tmp_path_factory.mktemp("llm-registry")
    monkeypatch.setenv("LLM_CALL_LOG_DIR", str(root / "llm-calls"))
    base = root / "ai-hub"
    if REAL_REGISTRY.exists():
        base.mkdir(parents=True)
        shutil.copy(REAL_REGISTRY, base / "llm-registry.toml")
        shutil.copytree(REAL_REGISTRY.parent / "prompts", base / "prompts")
    monkeypatch.setenv("LLM_REGISTRY", str(base / "llm-registry.toml"))
    llm_registry._reset()
    yield
    llm_registry._reset()
