"""layout_todo: one or two columns, everything on the board, and the "+N more" cut-off."""

from datetime import date, timedelta
from pathlib import Path

from whiteboard.todo.source import parse_plan
from whiteboard.todo.view import build_groups, build_payload, layout_todo
from whiteboard.todo.view.layout import MAX_FONT_PX, MIN_FONT_PX, ONE_COLUMN_MIN_FONT_PX
from whiteboard.todo.view.payload import HeaderText

TODAY = date(2026, 10, 19)
BOARD = (1114.0, 720.0)


def groups_with(rows_per_day: int, days: int = 7):
    lines = [
        f"- [ ] [chem-120] Item {day}.{n} (due {TODAY + timedelta(days=day)} 10:{n:02d})"
        for day in range(days)
        for n in range(rows_per_day)
    ]
    return build_groups(parse_plan("\n".join(lines), Path("plan.md"), TODAY), TODAY)


def inside_board(box) -> bool:
    return box.x >= 0 and box.y >= 0 and box.x + box.w <= BOARD[0] and box.y + box.h <= BOARD[1]


def test_a_short_list_is_one_big_column() -> None:
    layout = layout_todo(groups_with(1, days=2), BOARD)
    assert layout.metrics.font_px == MAX_FONT_PX
    assert {place.box.x for place in layout.rows} == {layout.body.x}
    assert all(place.text_x > place.box.x + layout.metrics.tag_w for place in layout.rows)


def test_a_long_list_goes_to_two_columns_and_stays_on_the_board() -> None:
    layout = layout_todo(groups_with(3), BOARD)
    assert layout.metrics.font_px >= MIN_FONT_PX
    assert len({place.box.x for place in layout.rows}) == 2 and layout.hidden_rows == 0
    assert all(inside_board(place.box) for place in layout.rows)


def test_too_much_is_cut_off_with_a_more_line() -> None:
    layout = layout_todo(groups_with(9), BOARD)
    assert layout.metrics.font_px == MIN_FONT_PX < ONE_COLUMN_MIN_FONT_PX
    assert layout.hidden_rows > 0 and layout.more is not None and inside_board(layout.more)
    assert len(layout.rows) + layout.hidden_rows == 63
    payload = build_payload(layout, HeaderText("Monday 19 October", "synced 06:00"), set())
    assert payload["more"]["label"] == f"+{layout.hidden_rows} more"
