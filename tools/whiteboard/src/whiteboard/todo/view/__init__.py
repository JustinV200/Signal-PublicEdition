"""Public API of whiteboard.todo.view: what the TODO view shows, where, and what changed.

sections groups the parsed lines (Overdue, today, tomorrow, this week, of note) with
short titles (titles) and due texts (labels), tracking diffs a
sync against the last one (newly done, done before today), layout places everything
in board pixels, and payload turns that into the page's JSON. TodoStore keeps the
tracking across restarts.
"""

from whiteboard.todo.view.labels import (
    DONE_LABEL,
    GROUP_OF_NOTE,
    GROUP_OVERDUE,
    GROUP_TODAY,
    GROUP_TOMORROW,
    GROUP_WEEK,
    MONTHS,
    WEEKDAYS,
    day_label,
    due_label,
    long_day_label,
)
from whiteboard.todo.view.layout import (
    Box,
    HeadingPlace,
    Metrics,
    RowPlace,
    TodoLayout,
    layout_todo,
)
from whiteboard.todo.view.payload import TAG_COLORS, HeaderText, build_payload, tag_color
from whiteboard.todo.view.sections import WINDOW_DAYS, GroupRow, TodoGroup, build_groups
from whiteboard.todo.view.store import TodoStore
from whiteboard.todo.view.titles import short_title
from whiteboard.todo.view.tracking import DoneTracking, TrackResult, track

__all__ = [
    "DONE_LABEL",
    "GROUP_OF_NOTE",
    "GROUP_OVERDUE",
    "GROUP_TODAY",
    "GROUP_TOMORROW",
    "GROUP_WEEK",
    "MONTHS",
    "TAG_COLORS",
    "WEEKDAYS",
    "WINDOW_DAYS",
    "Box",
    "DoneTracking",
    "GroupRow",
    "HeaderText",
    "HeadingPlace",
    "Metrics",
    "RowPlace",
    "TodoGroup",
    "TodoLayout",
    "TodoStore",
    "TrackResult",
    "build_groups",
    "build_payload",
    "day_label",
    "due_label",
    "layout_todo",
    "long_day_label",
    "short_title",
    "tag_color",
    "track",
]
