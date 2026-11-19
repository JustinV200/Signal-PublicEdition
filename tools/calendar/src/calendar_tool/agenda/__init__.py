"""Public API of calendar_tool.agenda: fetch, normalise and cache the upcoming events."""

from calendar_tool.agenda.cache import agenda_payload, sync_cache
from calendar_tool.agenda.fetch import DEFAULT_DAYS, MAX_DAYS, fetch_agenda
from calendar_tool.agenda.normalize import NO_TITLE, AgendaEvent, clean_text, normalize_event
from calendar_tool.agenda.refresh import refresh_cache
from calendar_tool.agenda.sync_status import describe_sync_status, record_sync_status

__all__ = [
    "DEFAULT_DAYS",
    "MAX_DAYS",
    "NO_TITLE",
    "AgendaEvent",
    "agenda_payload",
    "clean_text",
    "describe_sync_status",
    "fetch_agenda",
    "normalize_event",
    "record_sync_status",
    "refresh_cache",
    "sync_cache",
]
