from mpk_deck.config import (
    ACCENT_HEX,
    load_last_accent,
    load_last_always_on_top,
    load_last_knob_style,
    load_last_mode,
    load_last_theme,
    save_last_accent,
    save_last_always_on_top,
    save_last_knob_style,
    save_last_mode,
    save_last_theme,
)


def test_save_and_load_last_mode_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_mode("expanded", ini_path=ini_path)
    assert load_last_mode(ini_path=ini_path) == "expanded"


def test_load_last_mode_defaults_to_mini(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_mode(ini_path=ini_path) == "mini"


def test_save_and_load_last_theme_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_theme("light", ini_path=ini_path)
    assert load_last_theme(ini_path=ini_path) == "light"


def test_load_last_theme_defaults_to_dark(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_theme(ini_path=ini_path) == "dark"


def test_save_and_load_always_on_top_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_always_on_top(True, ini_path=ini_path)
    assert load_last_always_on_top(ini_path=ini_path) is True


def test_load_last_always_on_top_defaults_to_false(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_always_on_top(ini_path=ini_path) is False


def test_save_and_load_last_accent_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_accent("#7c5cff", ini_path=ini_path)
    assert load_last_accent(ini_path=ini_path) == "#7c5cff"


def test_load_last_accent_defaults_to_accent_hex(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_accent(ini_path=ini_path) == ACCENT_HEX


def test_save_and_load_last_knob_style_round_trip(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    save_last_knob_style("A", ini_path=ini_path)
    assert load_last_knob_style(ini_path=ini_path) == "A"


def test_load_last_knob_style_defaults_to_needle(tmp_path):
    ini_path = str(tmp_path / "settings.ini")
    assert load_last_knob_style(ini_path=ini_path) == "B"
