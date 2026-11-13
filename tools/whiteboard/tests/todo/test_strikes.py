"""Strike geometry: a line across a row's text is a cross-out; underlines and short marks aren't."""

import numpy as np
import pytest

from whiteboard.todo import StrikeTarget, strike_candidates

# Two rows, 30 px tall, text from x=200 to x=600, in a column from x=28 to x=1086.
COLUMN = {"font_px": 21, "row_x0": 28, "row_x1": 1086, "text": "item"}
FIRST = StrikeTarget("first", 200, 600, 100, 130, **COLUMN)
SECOND = StrikeTarget("second", 200, 600, 130, 160, **COLUMN)


def ink(*lines: tuple[int, int, int]) -> np.ndarray:
    """A 720x1114 mask with horizontal 3 px lines (x0, x1, y)."""
    mask = np.zeros((720, 1114), dtype=np.uint8)
    for x0, x1, y in lines:
        mask[y - 1 : y + 2, x0:x1] = 255
    return mask


def crossed(mask: np.ndarray, targets: list[StrikeTarget]) -> set[str]:
    return {candidate.target.id for candidate in strike_candidates(mask, targets)}


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ([(190, 560, 116)], {"first"}),
        ([(200, 600, 115), (180, 620, 146)], {"first", "second"}),
        # Thick ink from y=100 to 106: it reaches the band (from 106), but its centre is
        # 0.38 rows off the middle, like a neighbour's cross-out seen a bit low.
        ([(200, 600, 101), (200, 600, 104), (200, 600, 105)], set()),
    ],
    ids=["one row", "two rows at once", "a line along the row's edge"],
)
def test_a_line_through_the_middle_crosses_out_only_those_rows(
    lines: list[tuple[int, int, int]], expected: set[str]
) -> None:
    assert crossed(ink(*lines), [FIRST, SECOND]) == expected


def test_an_underline_or_a_short_mark_is_not_a_cross_out() -> None:
    underline = ink((200, 600, 128))
    short_mark = ink((200, 300, 115))
    assert crossed(underline, [FIRST, SECOND]) == set()
    assert crossed(short_mark, [FIRST, SECOND]) == set()


def test_on_a_short_item_a_tick_is_not_a_cross_out_but_a_line_across_is() -> None:
    # "A18" is about 32 px wide at font 21, so it's measured over 2 em (42 px).
    short = StrikeTarget("short", 200, 232, 100, 130, **COLUMN)
    tick = ink((205, 226, 115))  # 1 em
    assert crossed(tick, [short]) == set()
    assert crossed(ink((195, 240, 115)), [short]) == {"short"}
