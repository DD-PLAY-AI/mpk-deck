def needle_angle(value: float) -> float:
    """0.0 -> 210deg (7 o'clock), 1.0 -> 510deg (5 o'clock, i.e. 150deg mod 360),
    clockwise through 12 o'clock (300deg total travel). 0deg = up, increasing
    clockwise - matches QPainter.rotate()'s convention directly, no conversion
    needed at the call site. Returned unwrapped (can exceed 360) since
    QPainter.rotate() handles that correctly."""
    return 210.0 + max(0.0, min(1.0, value)) * 300.0
