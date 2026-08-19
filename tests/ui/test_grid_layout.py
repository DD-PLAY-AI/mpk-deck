from mpk_deck.ui.grid_layout import compute_pad_rects


def test_compute_pad_rects_returns_one_rect_per_cell():
    rects = compute_pad_rects(400, 200, cols=4, rows=2, margin=10, spacing=8)
    assert len(rects) == 8


def test_compute_pad_rects_cells_are_square():
    rects = compute_pad_rects(400, 200, cols=4, rows=2, margin=10, spacing=8)
    for rect in rects:
        assert rect.width() == rect.height()


def test_compute_pad_rects_row_major_order_left_to_right_top_to_bottom():
    rects = compute_pad_rects(400, 200, cols=4, rows=2, margin=10, spacing=8)
    # first row's y should match, sorted left-to-right by x
    top_row = rects[:4]
    xs = [r.x() for r in top_row]
    assert xs == sorted(xs)
    assert all(r.y() == top_row[0].y() for r in top_row)
    assert rects[4].y() > top_row[0].y()


def test_compute_pad_rects_fits_within_bounds():
    rects = compute_pad_rects(400, 200, cols=4, rows=2, margin=10, spacing=8)
    for rect in rects:
        assert rect.x() >= 0
        assert rect.y() >= 0
        assert rect.x() + rect.width() <= 400
        assert rect.y() + rect.height() <= 200


def test_compute_pad_rects_letterboxes_when_aspect_mismatched():
    # much wider than the 4:2 grid needs -> extra space on the sides, cells still square
    rects = compute_pad_rects(1000, 200, cols=4, rows=2, margin=10, spacing=8)
    widths = {r.width() for r in rects}
    assert len(widths) == 1
    total_grid_width = 4 * next(iter(widths)) + 3 * 8
    assert total_grid_width < 1000 - 2 * 10 - 1  # didn't stretch to fill leftover width


def test_compute_pad_rects_tiny_area_still_returns_positive_size():
    rects = compute_pad_rects(20, 20, cols=4, rows=2, margin=10, spacing=8)
    for rect in rects:
        assert rect.width() >= 1
        assert rect.height() >= 1
