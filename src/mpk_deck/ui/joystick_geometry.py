def clamp_deflection(dx: float, dy: float, max_radius: float) -> tuple[float, float]:
    """Clamp a raw pixel offset from center to a circle of max_radius, return axes
    normalized to [-1.0, 1.0] on each dimension. (0.0, 0.0) if max_radius <= 0."""
    if max_radius <= 0:
        return (0.0, 0.0)
    distance = (dx * dx + dy * dy) ** 0.5
    if distance > max_radius:
        scale = max_radius / distance
        dx *= scale
        dy *= scale
    return (dx / max_radius, dy / max_radius)
