"""Where the task grid's boxes go: the whiteboard-task-grid layout, coded once.

The layout is drawn for a 1114x720 board (the fitted board's usual size) and
scaled to the real one. Under a white header box sits a grid of 200 px tall
boxes from (30, 78): 3 columns of 340 (22 px gaps) for up to 7 active tasks,
else 4 columns of 255 (14 px gaps). The queued and done boxes always take the
last slots: with 8 active tasks they share the bottom row, 2 columns each;
with 9-10 they are single boxes in the last two slots. Past 10 active tasks
the least finished ones are left off (the header says how many).
"""

from dataclasses import dataclass

DESIGN_WIDTH, DESIGN_HEIGHT = 1114.0, 720.0
GRID_X, GRID_Y = 30.0, 78.0
BOX_HEIGHT, ROW_GAP = 200.0, 10.0
ROWS = 3
# (columns, box width, gap between columns)
THREE_COLUMNS = (3, 340.0, 22.0)
FOUR_COLUMNS = (4, 255.0, 14.0)
MAX_THREE_COLUMN_ACTIVE = 7
MAX_ACTIVE = 10
# The header box across the top, and where its two texts sit (inside x 45-900, which the
# physical board doesn't cut off).
HEADER_BOX = (30.0, 12.0, 1064.0, 56.0)
HEADER_TEXT = (45.0, 17.0, 640.0, 46.0)
USAGE_TEXT = (700.0, 15.0, 190.0, 50.0)


@dataclass(frozen=True)
class Box:
    """A rectangle in design pixels (1114x720)."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class GridPlan:
    """The boxes for one grid.

    Attributes:
        active: One box per shown active task, in reading order.
        queued: The grouped queued box.
        done: The grouped done box.
        hidden: Active tasks left off for lack of room.
    """

    active: tuple[Box, ...]
    queued: Box
    done: Box
    hidden: int


def plan_grid(active_count: int) -> GridPlan:
    """Lay out `active_count` active boxes plus the queued and done boxes."""
    shown = min(active_count, MAX_ACTIVE)
    if shown <= MAX_THREE_COLUMN_ACTIVE:
        slots = _slots(*THREE_COLUMNS)
        queued, done = slots[-2], slots[-1]
    elif shown == FOUR_COLUMNS[0] * (ROWS - 1):
        # 8 active fill two rows; queued and done split the bottom row.
        slots = _slots(*FOUR_COLUMNS)
        queued = _merge(slots[8], slots[9])
        done = _merge(slots[10], slots[11])
    else:
        slots = _slots(*FOUR_COLUMNS)
        queued, done = slots[-2], slots[-1]
    return GridPlan(tuple(slots[:shown]), queued, done, active_count - shown)


def _slots(columns: int, width: float, gap: float) -> list[Box]:
    return [
        Box(GRID_X + col * (width + gap), GRID_Y + row * (BOX_HEIGHT + ROW_GAP), width, BOX_HEIGHT)
        for row in range(ROWS)
        for col in range(columns)
    ]


def _merge(left: Box, right: Box) -> Box:
    return Box(left.x, left.y, right.x + right.w - left.x, left.h)
