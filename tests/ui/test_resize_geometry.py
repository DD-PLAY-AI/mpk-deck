from mpk_deck.ui.hit_test import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
)
from mpk_deck.ui.resize_geometry import compute_resized_rect

START = dict(x=100, y=100, w=200, h=100)  # aspect 2.0
ASPECT = 2.0


def test_east_grows_width_keeps_position_derives_height():
    x, y, w, h = compute_resized_rect(HTRIGHT, dx=40, dy=0, aspect=ASPECT, **START)
    assert (x, y) == (100, 100)
    assert w == 240
    assert h == 120  # 240 / 2.0


def test_west_grows_width_shifts_x_left():
    x, y, w, h = compute_resized_rect(HTLEFT, dx=-40, dy=0, aspect=ASPECT, **START)
    assert w == 240
    assert h == 120
    assert x == 60  # left edge moved left by 40, right edge fixed
    assert y == 100


def test_south_grows_height_keeps_position_derives_width():
    x, y, w, h = compute_resized_rect(HTBOTTOM, dx=0, dy=30, aspect=ASPECT, **START)
    assert (x, y) == (100, 100)
    assert h == 130
    assert w == 260  # 130 * 2.0


def test_north_grows_height_shifts_y_up():
    x, y, w, h = compute_resized_rect(HTTOP, dx=0, dy=-30, aspect=ASPECT, **START)
    assert h == 130
    assert w == 260
    assert x == 100
    assert y == 70  # top edge moved up by 30, bottom edge fixed


def test_southeast_corner_grows_from_top_left_anchor():
    x, y, w, h = compute_resized_rect(HTBOTTOMRIGHT, dx=40, dy=999, aspect=ASPECT, **START)
    # dy is ignored for E/W-driven corners; width drives, height derives
    assert (x, y) == (100, 100)
    assert w == 240
    assert h == 120


def test_northwest_corner_shifts_both_x_and_y():
    x, y, w, h = compute_resized_rect(HTTOPLEFT, dx=-40, dy=999, aspect=ASPECT, **START)
    assert w == 240
    assert h == 120
    assert x == 60  # right edge (300) fixed: 300 - 240
    assert y == 80  # bottom edge (200) fixed: 200 - 120


def test_southwest_corner_shifts_x_only():
    x, y, w, h = compute_resized_rect(HTBOTTOMLEFT, dx=-40, dy=999, aspect=ASPECT, **START)
    assert w == 240
    assert h == 120
    assert x == 60
    assert y == 100


def test_northeast_corner_shifts_y_only():
    x, y, w, h = compute_resized_rect(HTTOPRIGHT, dx=40, dy=999, aspect=ASPECT, **START)
    assert w == 240
    assert h == 120
    assert x == 100
    assert y == 80


def test_min_width_clamp_on_shrink():
    x, y, w, h = compute_resized_rect(HTRIGHT, dx=-1000, dy=0, aspect=ASPECT, min_w=120, **START)
    assert w == 120
    assert h == 60
