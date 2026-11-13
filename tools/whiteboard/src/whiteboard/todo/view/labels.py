"""Day names and the short texts the TODO view shows: day labels and each row's due text.

Fixed English names, so labels never depend on the daemon's locale. The idle view
shares WEEKDAYS and MONTHS.
"""

from datetime import date

from whiteboard.todo.source import PlanEntry

GROUP_OVERDUE = "overdue"
GROUP_TODAY = "today"
GROUP_TOMORROW = "tomorrow"
GROUP_WEEK = "week"
GROUP_OF_NOTE = "of_note"
# Shown instead of the due text on a row ticked today (with the check mark in its box).
DONE_LABEL = "✓ done"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LONG_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
LONG_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def day_label(day: date) -> str:
    """A short day label, e.g. "Wed 21 Oct"."""
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def long_day_label(day: date) -> str:
    """A long day label for the view's header, e.g. "Wednesday 21 October"."""
    return f"{LONG_WEEKDAYS[day.weekday()]} {day.day} {LONG_MONTHS[day.month - 1]}"


def due_label(entry: PlanEntry, group_key: str, today: date) -> str:
    """The due text at a row's right, by group.

    Overdue: how late ("3d late", or "late" undated). Today and tomorrow: the time,
    if any. This week: the weekday and time ("Wed 14:30"). Of note: the date.
    """
    due = entry.due
    if group_key == GROUP_OVERDUE:
        return f"{(today - due.day).days}d late" if due is not None else "late"
    if due is None:
        return ""
    if group_key == GROUP_WEEK:
        weekday = WEEKDAYS[due.day.weekday()]
        return f"{weekday} {due.time}" if due.time else weekday
    if group_key == GROUP_OF_NOTE:
        return day_label(due.day)
    return due.time or ""
