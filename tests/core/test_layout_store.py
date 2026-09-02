from pathlib import Path

import pytest

from mpk_deck.core.layout_store import (
    Layout,
    LayoutItem,
    generate_layout_id,
    load_layouts,
    save_layouts,
)


def _sample() -> dict[str, Layout]:
    return {
        "coding": Layout(
            name="코딩 셋업",
            items=[
                LayoutItem(
                    kind="program",
                    path="C:/x/Code.exe",
                    rect=(80, 60, 1280, 900),
                    title_match="Visual Studio Code",
                ),
                LayoutItem(
                    kind="url",
                    url="https://claude.ai/code",
                    browser="chrome",
                    rect=(1400, 60, 520, 900),
                    title_match="Claude",
                ),
                LayoutItem(kind="program", path="C:/x/chrome.exe", rect=(0, 0, 0, 0), maximized=True),
            ],
        )
    }


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    assert load_layouts(path) == _sample()


def test_save_writes_readable_korean(tmp_path):
    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    assert "코딩 셋업" in path.read_text(encoding="utf-8")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_layouts(tmp_path / "nope.yaml") == {}


def test_load_bad_yaml_returns_empty(tmp_path):
    path = tmp_path / "layouts.yaml"
    path.write_text("]: [: not yaml", encoding="utf-8")
    assert load_layouts(path) == {}


def test_load_skips_a_malformed_item_but_keeps_the_layout(tmp_path, caplog):
    path = tmp_path / "layouts.yaml"
    path.write_text(
        "layouts:\n"
        "  a:\n"
        "    name: A\n"
        "    items:\n"
        "      - kind: program\n"
        "        path: C:/x.exe\n"
        "        rect: [1, 2, 3, 4]\n"
        "      - kind: nonsense\n",
        encoding="utf-8",
    )
    layouts = load_layouts(path)
    assert list(layouts) == ["a"]
    assert len(layouts["a"].items) == 1


def test_save_failure_leaves_existing_file_intact(tmp_path, monkeypatch):
    import mpk_deck.core.layout_store as ls

    path = tmp_path / "layouts.yaml"
    save_layouts(_sample(), path)
    monkeypatch.setattr(ls.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        save_layouts({"x": Layout(name="x", items=[])}, path)
    assert load_layouts(path) == _sample()
    assert list(tmp_path.iterdir()) == [path]


def test_generate_layout_id_slugifies_and_dedupes():
    assert generate_layout_id("My Setup!", existing_ids=[]) == "my_setup"
    assert generate_layout_id("My Setup!", existing_ids=["my_setup"]) == "my_setup_2"
    assert generate_layout_id("   ", existing_ids=[]) == "layout"
