from PySide6.QtCore import QRect

NUM_KEYS = 25  # 2 octaves + 1, C to C, matching the physical MPK mini MK2 keybed
_BLACK_KEY_OFFSETS = {1, 3, 6, 8, 10}  # semitone offsets within an octave that are black keys

BLACK_KEY_WIDTH_RATIO = 0.6
BLACK_KEY_HEIGHT_RATIO = 0.62


def is_black_key(index: int) -> bool:
    """Whether semitone `index` (0 = C) is a black key, per the standard piano pattern."""
    return index % 12 in _BLACK_KEY_OFFSETS


def compute_keybed_rects(width: int, height: int) -> tuple[list[QRect], list[QRect]]:
    """Lay out a 15-white/10-black key piano keybed within (width, height).

    White keys tile the full width contiguously; black keys are narrower/shorter
    and centered on the boundary between the white keys they sit above.
    """
    num_white = NUM_KEYS - sum(is_black_key(i) for i in range(NUM_KEYS))
    white_w = width / num_white
    black_w = white_w * BLACK_KEY_WIDTH_RATIO
    black_h = height * BLACK_KEY_HEIGHT_RATIO

    white_rects: list[QRect] = []
    black_rects: list[QRect] = []
    white_index = 0
    for i in range(NUM_KEYS):
        if is_black_key(i):
            boundary_x = white_index * white_w
            black_rects.append(QRect(round(boundary_x - black_w / 2), 0, round(black_w), round(black_h)))
        else:
            white_rects.append(QRect(round(white_index * white_w), 0, round(white_w), height))
            white_index += 1
    return white_rects, black_rects
