from mpk_deck.ui.scaling import compute_scale


def test_compute_scale_at_base_width_is_one():
    assert compute_scale(480, base_width=480) == 1.0


def test_compute_scale_scales_up_proportionally():
    assert compute_scale(960, base_width=480) == 2.0


def test_compute_scale_scales_down_proportionally():
    assert compute_scale(240, base_width=480) == 0.5


def test_compute_scale_clamps_to_minimum():
    assert compute_scale(1, base_width=480) >= 0.5


def test_compute_scale_handles_zero_width():
    assert compute_scale(0, base_width=480) >= 0.5
