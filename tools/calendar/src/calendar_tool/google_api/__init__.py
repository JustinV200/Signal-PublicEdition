"""Public API of calendar_tool.google_api: the read-only Calendar REST client and its reads."""

from calendar_tool.google_api.client import API_BASE, CalendarClient, HttpSession
from calendar_tool.google_api.resources import (
    CalendarInfo,
    list_events,
    list_selected_calendars,
    primary_calendar_email,
)

__all__ = [
    "API_BASE",
    "CalendarClient",
    "CalendarInfo",
    "HttpSession",
    "list_events",
    "list_selected_calendars",
    "primary_calendar_email",
]
