"""The agenda JSON shape and `sync-cache`: fetch it all, then replace the cache atomically.

A failed fetch raises before anything is written, so the old cache stays in place.
"""

from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

from signal_jsonstate import StateFileError, write_json_atomic

from calendar_tool.agenda.fetch import DEFAULT_DAYS, fetch_agenda
from calendar_tool.agenda.normalize import AgendaEvent
from calendar_tool.errors import CalendarError
from calendar_tool.google_api import CalendarClient


def agenda_payload(
    events: list[AgendaEvent], updated: datetime, skipped: list[str]
) -> dict[str, Any]:
    """The cache file and `agenda --json` shape.

    {"updated": ISO 8601, "events": [...], "skipped": [names of calendars that failed]}.
    """
    return {
        "updated": updated.isoformat(timespec="seconds"),
        "events": [event.to_json() for event in events],
        "skipped": skipped,
    }


def sync_cache(
    client: CalendarClient, cache_path: Path, now: datetime, zone: tzinfo | None = None
) -> tuple[int, list[str]]:
    """Fetch the next DEFAULT_DAYS days and atomically replace `cache_path`.

    Args:
        client: The API client.
        cache_path: Usually paths.CACHE_PATH.
        now: Timezone-aware; also the "updated" stamp.
        zone: The zone for timed events; None means this PC's local time.

    Returns:
        (how many events were written, names of skipped calendars).

    Raises:
        CalendarError: The fetch or the write failed; the old cache is untouched.
    """
    events, skipped = fetch_agenda(client, now, DEFAULT_DAYS, zone)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(cache_path, agenda_payload(events, now.astimezone(zone), skipped))
    except (OSError, StateFileError) as error:
        raise CalendarError(f"Couldn't write {cache_path.name}: {error}") from None
    return len(events), skipped
