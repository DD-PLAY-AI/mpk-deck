from mpk_deck.ui.hit_test import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTCAPTION,
    HTCLIENT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
    classify_hit,
)

WIDTH, HEIGHT, BORDER = 200, 100, 6


def test_top_left_corner():
    assert classify_hit(2, 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTTOPLEFT


def test_top_right_corner():
    assert classify_hit(WIDTH - 2, 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTTOPRIGHT


def test_bottom_left_corner():
    assert classify_hit(2, HEIGHT - 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTBOTTOMLEFT


def test_bottom_right_corner():
    assert classify_hit(WIDTH - 2, HEIGHT - 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTBOTTOMRIGHT


def test_left_edge():
    assert classify_hit(2, HEIGHT // 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTLEFT


def test_right_edge():
    assert classify_hit(WIDTH - 2, HEIGHT // 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTRIGHT


def test_top_edge():
    assert classify_hit(WIDTH // 2, 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTTOP


def test_bottom_edge():
    assert classify_hit(WIDTH // 2, HEIGHT - 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTBOTTOM


def test_interior_over_interactive_widget_is_client():
    assert classify_hit(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT, BORDER, over_interactive=True) == HTCLIENT


def test_interior_over_empty_background_is_caption():
    assert classify_hit(WIDTH // 2, HEIGHT // 2, WIDTH, HEIGHT, BORDER, over_interactive=False) == HTCAPTION
