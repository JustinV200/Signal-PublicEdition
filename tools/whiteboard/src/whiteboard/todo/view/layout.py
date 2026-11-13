"""layout_todo: place the TODO view's header, headings and rows on the board, in board pixels.

The layout is worked out here rather than in the browser so the daemon knows where
every row is: a line the owner draws across a row on the real board is matched
against these boxes (whiteboard.todo.strikes). The page just draws what it's told.

Keynotes (the day's few AI-written lines, whiteboard.keynotes) get a fixed-size block
under the header when there are any; the list takes the rest.

Every line (heading or item) is one line-height tall, with a small gap between groups.
One column is used unless its font would drop below ONE_COLUMN_MIN_FONT_PX; then
two. If even two columns at MIN_FONT_PX can't hold everything, the tail is cut and
a "+N more" line says so. Text widths are estimated from character counts, which
is close enough for a strike check that only needs most of the text covered.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from whiteboard.todo.view.labels import DONE_LABEL
from whiteboard.todo.view.sections import GroupRow, TodoGroup

MARGIN_PX = 28.0
HEADER_HEIGHT_PX = 60.0
HEADER_GAP_PX = 14.0
GUTTER_PX = 40.0
MAX_FONT_PX = 34
MIN_FONT_PX = 14
# Below this, one column is too small to read across a room; two columns are used.
ONE_COLUMN_MIN_FONT_PX = 18
MAX_COLUMNS = 2
LINE_HEIGHT_EM = 1.45
GROUP_GAP_LINES = 0.45
# Sizes relative to the item font (the page's todo.css uses the same ratios).
CHECK_COLUMN_EM = 1.1
TAG_FONT_EM = 0.6
DUE_FONT_EM = 0.75
TEXT_GAP_EM = 0.45
# Average glyph widths in Segoe UI, as a fraction of the font size (measured roughly).
TEXT_CHAR_EM = 0.5
TAG_CHAR_EM = 0.6
TAG_PADDING_EM = 1.0
DUE_CHAR_EM = 0.55
# The due column always has room for the "done?" hint and a done row's label.
HINT_TEXT = "done?"
# The keynotes block: a small heading line, then one line per keynote, at a fixed size.
KEYNOTE_FONT_PX = 22.0
KEYNOTE_LINE_EM = 1.35
KEYNOTE_GAP_PX = 12.0
_FIT_SLACK = 1e-6

_HEADING, _ROW, _GAP, _MORE = "heading", "row", "gap", "more"


@dataclass(frozen=True)
class Box:
    """A rectangle in board pixels: top-left x, y and size."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class RowPlace:
    """Where one item is drawn.

    Attributes:
        row: The item and its due text.
        group_key: Its group (see sections.py).
        box: The whole row.
        text_x: Where the item text starts.
        text_w: Room for the text, up to the due column.
        ink_w: Estimated width of the rendered text (at most text_w), for strike checks.
    """

    row: GroupRow
    group_key: str
    box: Box
    text_x: float
    text_w: float
    ink_w: float


@dataclass(frozen=True)
class HeadingPlace:
    """Where a group heading is drawn."""

    group_key: str
    label: str
    box: Box


@dataclass(frozen=True)
class Metrics:
    """Sizes shared by every row, in board pixels."""

    font_px: float
    tag_font_px: float
    due_font_px: float
    check_w: float
    tag_w: float
    due_w: float


@dataclass(frozen=True)
class TodoLayout:
    """The whole view: header, body area, headings, rows, and the "+N more" line if any."""

    stage: tuple[float, float]
    header: Box
    body: Box
    metrics: Metrics
    headings: tuple[HeadingPlace, ...]
    rows: tuple[RowPlace, ...]
    more: Box | None
    hidden_rows: int
    keynotes: Box | None = None
    keynote_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Line:
    kind: str
    group: TodoGroup | None = None
    row: GroupRow | None = None

    @property
    def units(self) -> float:
        return GROUP_GAP_LINES if self.kind == _GAP else 1.0


def layout_todo(
    groups: Sequence[TodoGroup], stage: tuple[float, float], keynotes: Sequence[str] = ()
) -> TodoLayout:
    """Lay out the groups on a board of `stage` (width, height) pixels.

    Args:
        groups: What to list (build_groups).
        stage: The board's (width, height).
        keynotes: Today's keynote lines; none means no keynotes block.
    """
    width, height = stage
    header = Box(MARGIN_PX, MARGIN_PX, width - 2 * MARGIN_PX, HEADER_HEIGHT_PX)
    body_y = header.y + header.h + HEADER_GAP_PX
    keynote_box = None
    if keynotes:
        line_h = KEYNOTE_FONT_PX * KEYNOTE_LINE_EM
        keynote_box = Box(MARGIN_PX, body_y, header.w, (len(keynotes) + 1) * line_h)
        body_y += keynote_box.h + KEYNOTE_GAP_PX
    body = Box(MARGIN_PX, body_y, header.w, max(0.0, height - body_y - MARGIN_PX))
    lines = _lines(groups)
    font, columns, hidden_rows = _choose_columns(lines, body.h)
    metrics = _metrics(groups, font)
    headings, rows, more = _place(columns, body, metrics)
    places = (headings, rows, more, hidden_rows)
    return TodoLayout(stage, header, body, metrics, *places, keynote_box, tuple(keynotes))


def _lines(groups: Sequence[TodoGroup]) -> list[_Line]:
    """Headings and rows in order, with a gap line between groups."""
    lines: list[_Line] = []
    for group in groups:
        if lines:
            lines.append(_Line(_GAP))
        lines.append(_Line(_HEADING, group))
        lines += [_Line(_ROW, group, row) for row in group.rows]
    return lines


def _choose_columns(lines: list[_Line], body_h: float) -> tuple[float, list[list[_Line]], int]:
    """(font size, lines per column, rows cut off) for the most readable fit."""
    one = _largest_fit(lines, body_h, 1)
    if one is not None and one[0] >= ONE_COLUMN_MIN_FONT_PX:
        return one[0], one[1], 0
    two = _largest_fit(lines, body_h, MAX_COLUMNS)
    best = max((fit for fit in (one, two) if fit is not None), default=None, key=lambda f: f[0])
    if best is not None:
        return best[0], best[1], 0
    return _truncated(lines, body_h)


def _largest_fit(
    lines: list[_Line], body_h: float, column_count: int
) -> tuple[float, list[list[_Line]]] | None:
    """The biggest whole-pixel font at which every line fits, or None even at MIN_FONT_PX."""
    for font in range(MAX_FONT_PX, MIN_FONT_PX - 1, -1):
        columns = _fill(lines, body_h / (font * LINE_HEIGHT_EM), column_count)
        if columns is not None:
            return float(font), columns
    return None


def _truncated(lines: list[_Line], body_h: float) -> tuple[float, list[list[_Line]], int]:
    """Two columns at MIN_FONT_PX holding as many lines as fit, then a "+N more" line."""
    capacity = body_h / (MIN_FONT_PX * LINE_HEIGHT_EM)
    for keep in range(len(lines) - 1, -1, -1):
        columns = _fill([*lines[:keep], _Line(_MORE)], capacity, MAX_COLUMNS)
        if columns is not None:
            hidden = sum(1 for line in lines[keep:] if line.kind == _ROW)
            return float(MIN_FONT_PX), columns, hidden
    return float(MIN_FONT_PX), [[]], sum(1 for line in lines if line.kind == _ROW)


def _fill(lines: list[_Line], capacity: float, column_count: int) -> list[list[_Line]] | None:
    """Pour lines into columns of `capacity` line units; None if they don't all fit.

    A heading only starts a column if its first row fits under it, and a gap at
    the top of a column is dropped.
    """
    columns: list[list[_Line]] = [[]]
    used = 0.0
    for line in lines:
        if line.kind == _GAP and not columns[-1]:
            continue
        needed = line.units + (1.0 if line.kind == _HEADING else 0.0)
        if used + needed > capacity + _FIT_SLACK:
            if len(columns) == column_count or needed > capacity + _FIT_SLACK:
                return None
            columns.append([])
            used = 0.0
            if line.kind == _GAP:
                continue
        columns[-1].append(line)
        used += line.units
    return columns


def _metrics(groups: Sequence[TodoGroup], font: float) -> Metrics:
    """Row sizes at `font`: the tag column fits the longest tag, the due column the longest date."""
    rows = [row for group in groups for row in group.rows]
    longest_tag = max((len(row.entry.tag) for row in rows), default=0)
    longest_due = max([len(HINT_TEXT), len(DONE_LABEL), *(len(row.due_label) for row in rows)])
    tag_font = TAG_FONT_EM * font
    due_font = DUE_FONT_EM * font
    tag_w = (longest_tag * TAG_CHAR_EM + TAG_PADDING_EM) * tag_font if longest_tag else 0.0
    due_w = longest_due * DUE_CHAR_EM * due_font + TEXT_GAP_EM * font
    return Metrics(font, tag_font, due_font, CHECK_COLUMN_EM * font, tag_w, due_w)


def _place(
    columns: list[list[_Line]], body: Box, metrics: Metrics
) -> tuple[tuple[HeadingPlace, ...], tuple[RowPlace, ...], Box | None]:
    """Turn the poured columns into boxes."""
    count = len(columns)
    column_w = (body.w - (count - 1) * GUTTER_PX) / count
    line_h = metrics.font_px * LINE_HEIGHT_EM
    headings, rows, more = [], [], None
    for index, column in enumerate(columns):
        x, y = body.x + index * (column_w + GUTTER_PX), body.y
        for line in column:
            box = Box(x, y, column_w, line.units * line_h)
            y += box.h
            if line.kind == _HEADING and line.group is not None:
                headings.append(HeadingPlace(line.group.key, line.group.label, box))
            elif line.kind == _ROW and line.group is not None and line.row is not None:
                rows.append(_row_place(line.row, line.group.key, box, metrics))
            elif line.kind == _MORE:
                more = box
    return tuple(headings), tuple(rows), more


def _row_place(row: GroupRow, group_key: str, box: Box, metrics: Metrics) -> RowPlace:
    """Where the text sits in a row: after the checkbox and tag columns, before the due column."""
    gap = TEXT_GAP_EM * metrics.font_px if metrics.tag_w else 0.0
    text_x = box.x + metrics.check_w + metrics.tag_w + gap
    text_w = max(0.0, box.x + box.w - metrics.due_w - text_x)
    ink_w = min(len(row.title) * TEXT_CHAR_EM * metrics.font_px, text_w)
    return RowPlace(row, group_key, box, text_x, text_w, ink_w)
