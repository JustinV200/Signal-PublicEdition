"""strike_checks.looks_shifted: ink erased near the rows means a shift; the flicker along the
photo's border, which real snapshots show between almost every pair, doesn't."""

import numpy as np

from whiteboard.daemon.todo.strike_checks import looks_shifted
from whiteboard.todo import StrikeTarget

# Two rows of the real board's layout: 1114x720, rows 38 px tall from y=140.
BOARD_W, BOARD_H = 1114, 720
ROWS = [
    StrikeTarget(f"r{i}", 200, 600, 140 + 38 * i, 178 + 38 * i, 26, 28, 1086, "item")
    for i in range(2)
]


def mask(*boxes: tuple[int, int, int, int]) -> np.ndarray:
    """A board-sized ink mask, on in each (x0, x1, y0, y1) box."""
    ink = np.zeros((BOARD_H, BOARD_W), dtype=np.uint8)
    for x0, x1, y0, y1 in boxes:
        ink[y0:y1, x0:x1] = 255
    return ink


def test_flicker_on_the_border_is_not_a_shift_but_the_same_erasure_by_the_rows_is() -> None:
    cross_out = mask((190, 610, 157, 160))
    # Where real pairs flicker: 2 px down the left edge, along the bottom, and a strip
    # near the right edge where the fit meets the board's frame.
    border_flicker = mask((0, 2, 100, 220), (300, 400, 716, 718), (1100, 1111, 105, 213))
    assert not looks_shifted(cross_out, border_flicker, ROWS)
    old_ink_a_row_up = mask((100, 340, 119, 121))
    assert np.count_nonzero(old_ink_a_row_up) <= np.count_nonzero(border_flicker)
    assert looks_shifted(cross_out, old_ink_a_row_up, ROWS)


def test_erasing_under_the_floor_is_still_a_shift_against_little_added_ink() -> None:
    # 60 px erased is under SHIFT_ERASED_FLOOR_PX, but against 100 px added the ratio rule trips.
    assert looks_shifted(mask((200, 300, 157, 158)), mask((200, 260, 120, 121)), ROWS)
