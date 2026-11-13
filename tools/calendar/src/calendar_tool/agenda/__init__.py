"""Public API of calendar_tool.agenda: fetch, normalise and cache the upcoming events."""

from calendar_tool.agenda.cache import agenda_payload, sync_cache
from calendar_tool.agenda.fetch import DEFAULT_DAYS, fetch_agenda
from calendar_tool.agenda.normalize import AgendaEvent

__all__ = ["DEFAULT_DAYS", "AgendaEvent", "agenda_payload", "fetch_agenda", "sync_cache"]
