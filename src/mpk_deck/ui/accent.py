ACCENT_CHOICES: list[tuple[str, str]] = [
    ("blue", "#3a6df0"),
    ("violet", "#7c5cff"),
    ("teal", "#14b8a6"),
    ("coral", "#ff6b6b"),
    ("amber", "#f59e0b"),
    ("beige", "#c4a674"),
    ("gray", "#8a8f9c"),
]


def hex_to_rgb_str(hex_color: str) -> str:
    """"#3a6df0" -> "58,109,240" - matches config.ACCENT_RGB's existing format."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"{r},{g},{b}"


def mix(hex_color: str, target_rgb: tuple[int, int, int], amount: float) -> str:
    """Linearly interpolate hex_color toward target_rgb by amount (0.0..1.0).
    Used to derive lighter/darker gradient stops from whichever accent is active,
    without hand-authoring a light/dark pair per swatch."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    tr, tg, tb = target_rgb
    mr = round(r + (tr - r) * amount)
    mg = round(g + (tg - g) * amount)
    mb = round(b + (tb - b) * amount)
    return f"#{mr:02x}{mg:02x}{mb:02x}"
