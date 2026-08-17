import pytest
from mpk_deck.core.action_registry import Binding, load_bindings, save_bindings, ActionConfigError


def test_load_bindings_parses_valid_yaml(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: trigger\n"
        "    action: launch_program\n"
        "    params: { path: \"C:/x.exe\" }\n"
    )
    result = load_bindings(path)
    assert result == [
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"})
    ]


def test_load_bindings_skips_invalid_entry_and_keeps_valid_ones(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: bogus_type\n"
        "    action: launch_program\n"
        "  - control: pad_2\n"
        "    type: trigger\n"
        "    action: open_url\n"
        "    params: { url: \"https://example.com\" }\n"
    )
    result = load_bindings(path)
    assert len(result) == 1
    assert result[0].control == "pad_2"


def test_load_bindings_missing_file_raises(tmp_path):
    with pytest.raises(ActionConfigError):
        load_bindings(tmp_path / "nope.yaml")


def test_load_bindings_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("")
    assert load_bindings(path) == []


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "actions.yaml"
    bindings = [
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"}),
        Binding(control="knob_1", type="continuous", action="set_system_volume", params={}),
    ]
    save_bindings(path, bindings)
    assert load_bindings(path) == bindings
