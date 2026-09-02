from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    DEFAULT_BANK_ID,
    DEFAULT_BANK_NAME,
    DEFAULT_SWITCH_CONTROL,
    default_joystick_bindings,
    generate_bank_id,
    load_config,
    save_config,
)


def test_generate_bank_id_slugifies_name():
    assert generate_bank_id("Trading", existing_ids=[]) == "trading"


def test_generate_bank_id_replaces_non_alnum_with_underscore():
    assert generate_bank_id("My Cool Bank!", existing_ids=[]) == "my_cool_bank"


def test_generate_bank_id_dedupes_on_collision():
    assert generate_bank_id("Trading", existing_ids=["trading"]) == "trading_2"
    assert generate_bank_id("Trading", existing_ids=["trading", "trading_2"]) == "trading_3"


def test_generate_bank_id_blank_name_falls_back_to_bank():
    assert generate_bank_id("   ", existing_ids=[]) == "bank"


def test_default_joystick_bindings_covers_both_axes():
    bindings = default_joystick_bindings()
    by_control = {b.control: b for b in bindings}
    assert by_control["joystick_x"] == Binding(
        control="joystick_x", type="continuous", action="scroll_horizontal", params={"sensitivity": 1.0}
    )
    assert by_control["joystick_y"] == Binding(
        control="joystick_y", type="continuous", action="scroll_vertical", params={"sensitivity": 1.0}
    )


def test_default_joystick_bindings_returns_a_fresh_list_each_call():
    a = default_joystick_bindings()
    a.append(Binding(control="x", type="trigger", action="y", params={}))
    assert len(default_joystick_bindings()) == 2


def test_load_config_missing_file_returns_default_seed(tmp_path):
    config = load_config(tmp_path / "nope.yaml")
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}


def test_load_config_empty_file_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("")
    config = load_config(path)
    assert config.banks[DEFAULT_BANK_ID].name == DEFAULT_BANK_NAME


def test_load_config_malformed_yaml_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks: [this is not: valid: yaml: at all")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_migrates_old_flat_format(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: trigger\n"
        "    action: launch_program\n"
        '    params: { path: "C:/x.exe" }\n'
    )
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks[DEFAULT_BANK_ID].name == DEFAULT_BANK_NAME
    assert config.banks[DEFAULT_BANK_ID].bindings == [
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"}),
        *default_joystick_bindings(),
    ]


def test_load_config_migration_skips_invalid_entry(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "bindings:\n"
        "  - control: pad_1\n"
        "    type: bogus_type\n"
        "    action: launch_program\n"
        "  - control: pad_2\n"
        "    type: trigger\n"
        "    action: open_url\n"
        '    params: { url: "https://example.com" }\n'
    )
    config = load_config(path)
    non_joystick = [b for b in config.banks[DEFAULT_BANK_ID].bindings if b.control not in ("joystick_x", "joystick_y")]
    assert len(non_joystick) == 1
    assert non_joystick[0].control == "pad_2"


def test_load_config_parses_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "active_bank: bank_b\n"
        "switch_bindings:\n"
        "  key_0: bank_a\n"
        "banks:\n"
        "  bank_a:\n"
        "    name: Home\n"
        "    bindings: []\n"
        "  bank_b:\n"
        "    name: Trading\n"
        "    bindings:\n"
        "      - control: pad_1\n"
        "        type: trigger\n"
        "        action: open_url\n"
        '        params: { url: "https://example.com" }\n'
    )
    config = load_config(path)
    assert config.active_bank == "bank_b"
    assert config.switch_bindings == {"key_0": "bank_a"}
    assert config.banks["bank_a"] == Bank(name="Home", bindings=default_joystick_bindings())
    assert config.banks["bank_b"].name == "Trading"
    assert config.banks["bank_b"].bindings == [
        Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://example.com"}),
        *default_joystick_bindings(),
    ]


def test_load_config_non_mapping_top_level_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("- just\n- a\n- list\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_bank_entry_not_a_mapping_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\n  bank_a: not_a_mapping\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_switch_bindings_not_a_mapping_returns_default_seed(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\n  bank_a:\n    name: Home\n    bindings: []\nswitch_bindings:\n  - a\n  - b\n")
    config = load_config(path)
    assert config.active_bank == DEFAULT_BANK_ID


def test_load_config_null_banks_seeds_default_bank(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("banks:\nactive_bank: bank_a\n")
    config = load_config(path)
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=default_joystick_bindings())}


def test_load_config_active_bank_not_in_banks_falls_back(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("active_bank: ghost\nbanks:\n  bank_a:\n    name: Home\n    bindings: []\n")
    config = load_config(path)
    assert config.active_bank == "bank_a"


def test_load_config_preserves_existing_joystick_binding_instead_of_backfilling(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text(
        "active_bank: bank_a\n"
        "switch_bindings: {}\n"
        "banks:\n"
        "  bank_a:\n"
        "    name: Home\n"
        "    bindings:\n"
        "      - control: joystick_x\n"
        "        type: continuous\n"
        "        action: scroll_horizontal\n"
        "        params: { sensitivity: 2.5 }\n"
    )
    config = load_config(path)
    bindings = config.banks["bank_a"].bindings
    joystick_x = [b for b in bindings if b.control == "joystick_x"]
    joystick_y = [b for b in bindings if b.control == "joystick_y"]
    assert len(joystick_x) == 1
    assert joystick_x[0].params == {"sensitivity": 2.5}
    assert len(joystick_y) == 1  # still backfilled - only joystick_x was customized


def test_save_then_load_round_trips_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    config = DeckConfig(
        active_bank="bank_b",
        switch_bindings={"key_0": "bank_a"},
        banks={
            "bank_a": Bank(name="Home", bindings=default_joystick_bindings()),
            "bank_b": Bank(
                name="Trading",
                bindings=[
                    Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://x.com"}),
                    *default_joystick_bindings(),
                ],
            ),
        },
    )
    save_config(path, config)
    assert load_config(path) == config


def test_binding_label_round_trips_and_empty_labels_are_omitted(tmp_path):
    path = tmp_path / "actions.yaml"
    config = DeckConfig(
        active_bank="bank_a",
        switch_bindings={},
        banks={
            "bank_a": Bank(
                name="Home",
                bindings=[
                    Binding(control="pad_1", type="trigger", action="open_url", params={"url": "u"}, label="내 링크"),
                    Binding(control="pad_2", type="trigger", action="open_url", params={"url": "v"}),
                    *default_joystick_bindings(),
                ],
            )
        },
    )
    save_config(path, config)
    text = path.read_text(encoding="utf-8")
    assert "내 링크" in text  # allow_unicode - not \uXXXX escaped
    assert text.count("label:") == 1  # the empty one is dropped

    back = load_config(path)
    by_control = {b.control: b for b in back.banks["bank_a"].bindings}
    assert by_control["pad_1"].label == "내 링크"
    assert by_control["pad_2"].label == ""


def test_binding_icon_round_trips(tmp_path):
    path = tmp_path / "actions.yaml"
    svg = '<circle cx="32" cy="32" r="12" fill="none" stroke="{accent}" stroke-width="5"/>'
    config = DeckConfig(
        active_bank="bank_a",
        switch_bindings={},
        banks={"bank_a": Bank(name="Home", bindings=[
            Binding(control="pad_1", type="trigger", action="open_url", params={"url": "u"}, icon=svg),
            *default_joystick_bindings(),
        ])},
    )
    save_config(path, config)
    back = load_config(path)
    by_control = {b.control: b for b in back.banks["bank_a"].bindings}
    assert by_control["pad_1"].icon == svg
    assert by_control["joystick_x"].icon == ""  # empty icon omitted + parses back to ""


def test_save_config_failure_leaves_existing_file_intact(tmp_path, monkeypatch):
    import mpk_deck.core.action_registry as reg

    path = tmp_path / "actions.yaml"
    good = DeckConfig(
        active_bank="bank_a",
        switch_bindings={"key_0": "bank_a"},
        banks={"bank_a": Bank(name="Home", bindings=default_joystick_bindings())},
    )
    save_config(path, good)

    monkeypatch.setattr(reg.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    try:
        save_config(path, DeckConfig(active_bank="x", switch_bindings={}, banks={}))
    except OSError:
        pass

    assert load_config(path) == good  # old config untouched
    assert list(tmp_path.iterdir()) == [path]  # no leftover .tmp file
