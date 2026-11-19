"""build_actions: CalendarActions wired to the real sign-in, settings file and agenda cache."""

from calendar_tool.auth import open_client
from calendar_tool.paths import (
    CACHE_PATH,
    CLIENT_SECRETS_PATH,
    CONFIG_PATH,
    SYNC_STATUS_PATH,
    TOKEN_PATH,
)
from calendar_tool.service.actions import Backend, CalendarActions, gate_from_settings


def build_actions() -> CalendarActions:
    """The production CalendarActions. Nothing is opened until a call needs it."""
    backend = Backend(
        build_client=lambda: open_client(CLIENT_SECRETS_PATH, TOKEN_PATH),
        build_gate=lambda: gate_from_settings(CONFIG_PATH),
        cache_path=CACHE_PATH,
        status_path=SYNC_STATUS_PATH,
    )
    return CalendarActions(backend)
