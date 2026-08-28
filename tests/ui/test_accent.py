from mpk_deck.ui.accent import ACCENT_CHOICES, hex_to_rgb_str, mix


def test_accent_choices_first_entry_is_current_default():
    assert ACCENT_CHOICES[0] == ("blue", "#3a6df0")


def test_accent_choices_has_seven_entries():
    assert len(ACCENT_CHOICES) == 7


def test_accent_choices_names_are_unique():
    names = [name for name, _ in ACCENT_CHOICES]
    assert len(names) == len(set(names))


def test_hex_to_rgb_str_matches_existing_accent_rgb_format():
    assert hex_to_rgb_str("#3a6df0") == "58,109,240"


def test_mix_zero_amount_returns_original():
    assert mix("#3a6df0", (255, 255, 255), 0.0) == "#3a6df0"


def test_mix_full_amount_returns_target():
    assert mix("#3a6df0", (255, 255, 255), 1.0) == "#ffffff"


def test_mix_toward_black_at_half():
    assert mix("#3a6df0", (0, 0, 0), 0.5) == "#1d3678"


def test_mix_toward_white_at_045():
    assert mix("#3a6df0", (255, 255, 255), 0.45) == "#93aff7"
