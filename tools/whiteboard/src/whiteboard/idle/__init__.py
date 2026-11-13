"""Public API of whiteboard.idle: the idle view's logic, free of the daemon and web server.

The idle view is the board's default when nothing is drawn: clock, date, weather,
today's tasks, priorities, agent tasks, upcoming dates and a news ticker. Everything is
picked by fixed rules, with no model anywhere (refdocs/research/idle-board/plan.md).
- `rules`: when the board switches to it by itself.
- `sources`: each region's data from the plans, task list, usage, calendar and feed.
- `chips`: course chips (short name and colour).
The daemon wires these to the board (whiteboard.daemon.idle); the page is static/idle/.
"""

from whiteboard.idle.chips import parse_tag_labels
from whiteboard.idle.rules import day_view, should_go_idle, track_empty
from whiteboard.idle.sources import (
    MAX_FEED_BYTES,
    MAX_HEADLINES,
    DatedItem,
    NewsError,
    agents_region,
    overdue_count,
    parse_headlines,
    read_agenda,
    read_priorities,
    today_rows,
    upcoming_items,
    upcoming_rows,
    usage_line,
)
from whiteboard.idle.text import clean_text

__all__ = [
    "MAX_FEED_BYTES",
    "MAX_HEADLINES",
    "DatedItem",
    "NewsError",
    "agents_region",
    "clean_text",
    "day_view",
    "overdue_count",
    "parse_headlines",
    "parse_tag_labels",
    "read_agenda",
    "read_priorities",
    "should_go_idle",
    "today_rows",
    "track_empty",
    "upcoming_items",
    "upcoming_rows",
    "usage_line",
]
