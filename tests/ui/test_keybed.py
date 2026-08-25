from mpk_deck.ui.keybed import NUM_KEYS, compute_keybed_rects, is_black_key


def test_is_black_key_matches_standard_octave_pattern():
    black = {i for i in range(NUM_KEYS) if is_black_key(i)}
    assert black == {1, 3, 6, 8, 10, 13, 15, 18, 20, 22}


def test_is_black_key_final_key_is_white():
    assert is_black_key(NUM_KEYS - 1) is False


def test_compute_keybed_rects_counts():
    white, black = compute_keybed_rects(600, 100)
    assert len(white) == 15
    assert len(black) == 10


def test_compute_keybed_rects_white_keys_tile_left_to_right():
    white, _ = compute_keybed_rects(600, 100)
    xs = [r.x() for r in white]
    assert xs == sorted(xs)
    assert white[0].x() == 0
    assert white[-1].x() + white[-1].width() <= 600
    assert white[0].height() == 100


def test_compute_keybed_rects_black_keys_are_narrower_and_shorter():
    white, black = compute_keybed_rects(600, 100)
    for b in black:
        assert b.width() < white[0].width()
        assert b.height() < white[0].height()


def test_compute_keybed_rects_black_keys_sit_on_white_key_boundaries():
    white, black = compute_keybed_rects(600, 100)
    boundary_xs = {w.x() + w.width() for w in white[:-1]}
    for b in black:
        center = b.x() + b.width() / 2
        assert min(abs(center - bx) for bx in boundary_xs) < 2


def test_compute_keybed_rects_no_black_key_between_e_f_or_b_c():
    white, black = compute_keybed_rects(600, 100)
    # boundary after the 3rd white key (E-F) and after the 7th (B-C) have no black key
    no_black_boundaries = {white[2].x() + white[2].width(), white[6].x() + white[6].width()}
    for b in black:
        center = b.x() + b.width() / 2
        for boundary in no_black_boundaries:
            assert abs(center - boundary) > 2
