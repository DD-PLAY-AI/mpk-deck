from mpk_deck.config import load_last_mode, load_last_theme, save_last_mode, save_last_theme


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
