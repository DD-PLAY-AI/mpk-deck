from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    DEFAULT_BANK_ID,
    DEFAULT_BANK_NAME,
    DEFAULT_SWITCH_CONTROL,
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


def test_load_config_missing_file_returns_default_seed(tmp_path):
    config = load_config(tmp_path / "nope.yaml")
    assert config.active_bank == DEFAULT_BANK_ID
    assert config.switch_bindings == {DEFAULT_SWITCH_CONTROL: DEFAULT_BANK_ID}
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])}


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
        Binding(control="pad_1", type="trigger", action="launch_program", params={"path": "C:/x.exe"})
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
    bindings = config.banks[DEFAULT_BANK_ID].bindings
    assert len(bindings) == 1
    assert bindings[0].control == "pad_2"


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
    assert config.banks["bank_a"] == Bank(name="Home", bindings=[])
    assert config.banks["bank_b"].name == "Trading"
    assert config.banks["bank_b"].bindings == [
        Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://example.com"})
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
    assert config.banks == {DEFAULT_BANK_ID: Bank(name=DEFAULT_BANK_NAME, bindings=[])}


def test_load_config_active_bank_not_in_banks_falls_back(tmp_path):
    path = tmp_path / "actions.yaml"
    path.write_text("active_bank: ghost\nbanks:\n  bank_a:\n    name: Home\n    bindings: []\n")
    config = load_config(path)
    assert config.active_bank == "bank_a"


def test_save_then_load_round_trips_new_format(tmp_path):
    path = tmp_path / "actions.yaml"
    config = DeckConfig(
        active_bank="bank_b",
        switch_bindings={"key_0": "bank_a"},
        banks={
            "bank_a": Bank(name="Home", bindings=[]),
            "bank_b": Bank(
                name="Trading",
                bindings=[
                    Binding(control="pad_1", type="trigger", action="open_url", params={"url": "https://x.com"})
                ],
            ),
        },
    )
    save_config(path, config)
    assert load_config(path) == config
