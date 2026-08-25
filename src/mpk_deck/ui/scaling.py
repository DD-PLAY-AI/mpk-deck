MIN_SCALE = 0.5


def compute_scale(width: int, *, base_width: int) -> float:
    """Uniform scale factor for fixed-size controls, relative to the layout's base width."""
    return max(MIN_SCALE, width / base_width)
