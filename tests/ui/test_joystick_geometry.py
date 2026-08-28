import pytest

from mpk_deck.ui.joystick_geometry import clamp_deflection


def test_clamp_deflection_center_returns_zero():
    assert clamp_deflection(0.0, 0.0, 20.0) == (0.0, 0.0)


def test_clamp_deflection_inside_circle_normalizes_without_clamping():
    x, y = clamp_deflection(10.0, 0.0, 20.0)
    assert x == 0.5
    assert y == 0.0


def test_clamp_deflection_on_boundary_normalizes_to_one():
    x, y = clamp_deflection(0.0, -20.0, 20.0)
    assert x == 0.0
    assert y == -1.0


def test_clamp_deflection_outside_circle_is_clamped_to_radius():
    x, y = clamp_deflection(40.0, 0.0, 20.0)
    assert x == pytest.approx(1.0)
    assert y == pytest.approx(0.0, abs=1e-9)


def test_clamp_deflection_diagonal_outside_circle_preserves_direction():
    x, y = clamp_deflection(30.0, 30.0, 20.0)
    magnitude = (x * x + y * y) ** 0.5
    assert magnitude == pytest.approx(1.0)
    assert x == pytest.approx(y)


def test_clamp_deflection_zero_radius_returns_zero():
    assert clamp_deflection(5.0, 5.0, 0.0) == (0.0, 0.0)
