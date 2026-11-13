"""The UPCOMING region: dated items from the week plans and the calendar, merged by date.

Both sources give DatedItems (plan_items.upcoming_items, agenda.read_agenda); this
sorts them by day then time (untimed last on their day) and adds the day column:
"Today", the weekday ("Wed"), or the date ("4 Nov") past six days, where the weekday
would repeat today's.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from whiteboard.idle.chips import Chip
from whiteboard.todo.view import MONTHS, WEEKDAYS

TODAY_LABEL = "Today"
# Past this many days ahead the weekday would repeat today's, so the date is shown.
WEEKDAY_DAYS = 6
# Sorts after any HH:MM, so untimed items come last on their day.
END_OF_DAY = "24:00"


@dataclass(frozen=True)
class DatedItem:
    """One row's data.

    Attributes:
        day: The local date it falls on.
        time: "HH:MM" (local) or None for all-day items and end-of-day deadlines.
        chip: The course chip, or the calendar's.
        text: The title, with the time already in it when there is one.
    """

    day: date
    time: str | None
    chip: Chip | None
    text: str


def short_day(day: date, today: date) -> str:
    """The day column: Today, the weekday (Wed), or the date (4 Nov) past WEEKDAY_DAYS."""
    if day == today:
        return TODAY_LABEL
    if 0 < (day - today).days <= WEEKDAY_DAYS:
        return WEEKDAYS[day.weekday()]
    return f"{day.day} {MONTHS[day.month - 1]}"


def upcoming_rows(items: Iterable[DatedItem], today: date) -> list[dict[str, Any]]:
    """The region's rows, soonest first (the page shows as many as fit, then "+N more").

    Args:
        items: Plan and calendar items, in any order.
        today: The board's today.
    """
    ordered = sorted(items, key=lambda item: (item.day, item.time or END_OF_DAY))
    return [
        {
            "day": short_day(item.day, today),
            "today": item.day == today,
            "chip": item.chip,
            "text": item.text,
        }
        for item in ordered
    ]
