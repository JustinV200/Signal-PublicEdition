"""The calendar side of UPCOMING: events from tools/calendar's agenda cache.

tools/calendar keeps `.state/agenda.json`:
`{"updated": ISO, "events": [{"start", "end", "all_day", "title", "calendar"}]}`, where
start and end are ISO datetimes, or YYYY-MM-DD for all-day events (end exclusive, as
Google gives it). The idle view only reads it and never holds a calendar token. A
missing, invalid or stale (over MAX_AGE) file means no events: the plan's items still
show. Titles come from invites anyone can send, so they're cleaned and capped
(text.clean_text) and the page sets them as text.
"""

import logging
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

from signal_jsonstate import read_json_object

from whiteboard.idle.chips import CALENDAR_CHIP
from whiteboard.idle.sources.upcoming import DatedItem
from whiteboard.idle.text import clean_text

log = logging.getLogger(__name__)

MAX_AGE = timedelta(hours=2)
MAX_TITLE_CHARS = 80
ISO_DATE_CHARS = len("2026-10-20")


def read_agenda(
    path: Path, now: datetime, last_day: date, zone: tzinfo | None = None
) -> list[DatedItem]:
    """Calendar events from now to `last_day`, or [] when the cache is missing or unusable.

    Args:
        path: tools/calendar/.state/agenda.json.
        now: Local time now (aware). Events that have ended are left out.
        last_day: The window's last day.
        zone: The zone event times are shown in; None for the PC's own zone, with the
            offset that applies on each event's date (not today's: DST may differ).

    Raises:
        StateFileError: The file exists but can't be read right now (keep the last copy).
    """
    data = read_json_object(path)
    updated = _moment(data.get("updated"))
    if updated is None or now - updated > MAX_AGE or not isinstance(data.get("events"), list):
        return []
    items = []
    for raw in data["events"]:
        try:
            item = _event(raw, now, zone)
        except (TypeError, ValueError, KeyError, AttributeError) as error:
            log.debug("skipping a bad agenda event: %s", error)
            continue
        if item is not None and now.date() <= item.day <= last_day:
            items.append(item)
    return items


def _event(raw: Any, now: datetime, zone: tzinfo | None) -> DatedItem | None:
    """One event as a row, or None if it has ended or has no title.

    Raises:
        TypeError, ValueError, KeyError, AttributeError: A field is missing or malformed.
    """
    title = clean_text(raw["title"], MAX_TITLE_CHARS)
    start, end = raw["start"], raw.get("end")
    if not title:
        return None
    if raw.get("all_day") or len(start) == ISO_DATE_CHARS:
        first = date.fromisoformat(start[:ISO_DATE_CHARS])
        last = date.fromisoformat(end[:ISO_DATE_CHARS]) - timedelta(days=1) if end else first
        if last < now.date():
            return None
        # A multi-day event that began earlier shows on today.
        return DatedItem(max(first, now.date()), None, CALENDAR_CHIP, title)
    begins = _moment(start)
    ends = _moment(end) if end else begins
    if begins is None or ends is None or ends < now:
        return None
    local = begins.astimezone(zone)
    if local.date() < now.date():
        # Began on an earlier day and still on: shown today, untimed, like all-day events.
        return DatedItem(now.date(), None, CALENDAR_CHIP, title)
    time = f"{local:%H:%M}"
    return DatedItem(local.date(), time, CALENDAR_CHIP, f"{title} {time}")


def _moment(value: Any) -> datetime | None:
    """An aware datetime from ISO text (a naive one is taken as local), or None."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.astimezone()
