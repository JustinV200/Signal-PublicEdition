"""fetch_agenda: the next N days across every selected calendar, normalised and sorted."""

from datetime import datetime, timedelta, tzinfo

from calendar_tool.agenda.normalize import AgendaEvent, normalize_event
from calendar_tool.errors import ApiError
from calendar_tool.google_api import CalendarClient, list_events, list_selected_calendars

DEFAULT_DAYS = 14


def fetch_agenda(
    client: CalendarClient, now: datetime, days: int = DEFAULT_DAYS, zone: tzinfo | None = None
) -> tuple[list[AgendaEvent], list[str]]:
    """Every event overlapping [now, now + days) on the selected calendars, sorted by start.

    A calendar whose events the API refuses (ApiError, e.g. a 403 on a shared
    calendar that's still ticked but no longer readable) is skipped, so one bad
    calendar doesn't blank the rest. Network and sign-in failures still raise, and
    so does the API error when every calendar fails (that's not one bad calendar).

    Args:
        client: The API client.
        now: A timezone-aware "now"; ongoing events are included.
        days: How far ahead to look.
        zone: The zone for timed events; None means this PC's local time.

    Returns:
        (events sorted with all-day before timed on the same day, names of skipped calendars).

    Raises:
        CalendarError: Listing the calendars failed, every calendar failed, or a
            network or sign-in failure.
    """
    until = now + timedelta(days=days)
    events, skipped = [], []
    calendars = list_selected_calendars(client)
    for calendar in calendars:
        try:
            raws = list_events(client, calendar.calendar_id, now, until)
        except ApiError:
            if len(skipped) + 1 == len(calendars):
                raise
            skipped.append(calendar.name)
            continue
        for raw in raws:
            event = normalize_event(raw, calendar.name, zone)
            if event is not None:
                events.append(event)
    return sorted(events, key=AgendaEvent.sort_key), skipped
