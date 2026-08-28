from mpk_deck.ui.knob_geometry import needle_angle


def test_needle_angle_min_is_210():
    assert needle_angle(0.0) == 210.0


def test_needle_angle_max_is_510():
    assert needle_angle(1.0) == 510.0


def test_needle_angle_mid_is_360():
    assert needle_angle(0.5) == 360.0


def test_needle_angle_clamps_below_zero():
    assert needle_angle(-0.5) == 210.0


def test_needle_angle_clamps_above_one():
    assert needle_angle(1.5) == 510.0
