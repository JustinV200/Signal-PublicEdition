"""Public API of whiteboard.idle.sources: each idle region's data, from its source.

Pure functions over files already read or bodies already fetched (the daemon's
IdleController does the reading, timing and fetching).
"""

from whiteboard.idle.sources.agenda import read_agenda
from whiteboard.idle.sources.agents import agents_region, usage_line
from whiteboard.idle.sources.news import MAX_FEED_BYTES, MAX_HEADLINES, NewsError, parse_headlines
from whiteboard.idle.sources.plan_items import overdue_count, today_rows, upcoming_items
from whiteboard.idle.sources.priorities import read_priorities
from whiteboard.idle.sources.upcoming import DatedItem, upcoming_rows

__all__ = [
    "MAX_FEED_BYTES",
    "MAX_HEADLINES",
    "DatedItem",
    "NewsError",
    "agents_region",
    "overdue_count",
    "parse_headlines",
    "read_agenda",
    "read_priorities",
    "today_rows",
    "upcoming_items",
    "upcoming_rows",
    "usage_line",
]
