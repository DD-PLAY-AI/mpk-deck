from PySide6.QtCore import QRect


def compute_pad_rects(
    width: int,
    height: int,
    *,
    cols: int,
    rows: int,
    margin: int,
    spacing: int,
) -> list[QRect]:
    """Lay out cols*rows square cells within (width, height), letterboxed and centered."""
    usable_w = max(0, width - 2 * margin - (cols - 1) * spacing)
    usable_h = max(0, height - 2 * margin - (rows - 1) * spacing)
    cell = max(1, min(usable_w // cols, usable_h // rows))

    grid_w = cols * cell + (cols - 1) * spacing
    grid_h = rows * cell + (rows - 1) * spacing
    offset_x = (width - grid_w) // 2
    offset_y = (height - grid_h) // 2

    rects = []
    for row in range(rows):
        for col in range(cols):
            x = offset_x + col * (cell + spacing)
            y = offset_y + row * (cell + spacing)
            rects.append(QRect(x, y, cell, cell))
    return rects
