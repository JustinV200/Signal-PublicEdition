"""Public API of whiteboard.todo: the TODO view's logic, free of the daemon, camera and web server.

- `source`: read this and next week's plans from life/, and tick one checkbox back.
- `view`: group, diff, lay out and serialize what the board shows.
- `strikes`: which laid-out rows a new line of marker ink crosses out.
- `plan_frame`: the frame plan text goes in when a model reads it (data, never instructions).
The daemon wires these to the board (whiteboard.daemon.todo).
"""

from whiteboard.todo.plan_frame import PLAN_DATA_CLOSE, PLAN_DATA_NOTE, PLAN_DATA_OPEN, plan_data
from whiteboard.todo.source import (
    PlanEditError,
    PlanEntry,
    TodoLookupError,
    WeekPlan,
    find_entries,
    read_week_entries,
    set_line_done,
    week_folder_name,
)
from whiteboard.todo.strikes import (
    StrikeCandidate,
    StrikeTarget,
    strike_candidates,
    strike_coverage,
)
from whiteboard.todo.view import (
    GROUP_OF_NOTE,
    GROUP_OVERDUE,
    WINDOW_DAYS,
    DoneTracking,
    HeaderText,
    RowPlace,
    TodoGroup,
    TodoLayout,
    TodoStore,
    TrackResult,
    build_groups,
    build_payload,
    layout_todo,
    long_day_label,
    track,
)

__all__ = [
    "GROUP_OF_NOTE",
    "GROUP_OVERDUE",
    "PLAN_DATA_CLOSE",
    "PLAN_DATA_NOTE",
    "PLAN_DATA_OPEN",
    "WINDOW_DAYS",
    "DoneTracking",
    "HeaderText",
    "PlanEditError",
    "PlanEntry",
    "RowPlace",
    "StrikeCandidate",
    "StrikeTarget",
    "TodoGroup",
    "TodoLayout",
    "TodoLookupError",
    "TodoStore",
    "TrackResult",
    "WeekPlan",
    "build_groups",
    "build_payload",
    "find_entries",
    "layout_todo",
    "long_day_label",
    "plan_data",
    "read_week_entries",
    "set_line_done",
    "strike_candidates",
    "strike_coverage",
    "track",
    "week_folder_name",
]
