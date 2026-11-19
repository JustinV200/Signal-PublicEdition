"""CalendarActions: what the CLI and MCP server both run, wired to a sign-in, gate and cache.

Each call opens the client fresh (so a new `calendar add` counts at once, and
the MCP server starts with no sign-in), reads the gate setting fresh (so an
edited calendar.toml counts at once), and after a successful write refreshes
the idle board's agenda cache.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

from calendar_tool.agenda import (
    DEFAULT_DAYS,
    MAX_DAYS,
    AgendaEvent,
    agenda_payload,
    fetch_agenda,
    refresh_cache,
)
from calendar_tool.changes import (
    ChangeGate,
    EventChanges,
    EventEdit,
    EventRef,
    NewEvent,
    load_settings,
)
from calendar_tool.errors import CalendarError
from calendar_tool.google_api import CalendarClient

# What the CLI and the MCP server say when a write's cache refresh failed.
NOT_REFRESHED = "The idle board's agenda couldn't be refreshed; its scheduled sync will catch up."


@dataclass(frozen=True)
class Backend:
    """Where CalendarActions gets its client and gate, and where the cache lives.

    Attributes:
        build_client: Opens the stored sign-in (tests pass a fake-session client).
        build_gate: The ChangeGate from current settings (tests pass a fake dialog).
        cache_path, status_path: The agenda cache and its sync status file.
        zone: The zone for local times; None means this PC's.
    """

    build_client: Callable[[], CalendarClient]
    build_gate: Callable[[], ChangeGate]
    cache_path: Path
    status_path: Path
    zone: tzinfo | None = None


@dataclass(frozen=True)
class WriteResult:
    """A write's outcome: the event as written (None after a delete), and the cache refresh."""

    event: AgendaEvent | None
    is_board_refreshed: bool


def gate_from_settings(config_path: Path, zone: tzinfo | None = None) -> ChangeGate:
    """The real ChangeGate, on or off per `[changes] confirm` in config_path.

    Raises:
        SetupError: The config file is invalid.
    """
    return ChangeGate(load_settings(config_path).changes_confirm, zone=zone)


class CalendarActions:
    """The agenda read and the four writes, each a blocking call."""

    def __init__(self, backend: Backend) -> None:
        """Args: backend: the client, gate and cache paths."""
        self._backend = backend

    def agenda(self, days: int = DEFAULT_DAYS) -> dict[str, Any]:
        """The next `days` days (1-MAX_DAYS) with each event's ids and flags.

        Raises:
            CalendarError: A bad `days`, no sign-in, or the reads failed.
        """
        if not 1 <= days <= MAX_DAYS:
            raise CalendarError(f"days must be 1-{MAX_DAYS}.")
        now = datetime.now(self._backend.zone).astimezone(self._backend.zone)
        events, skipped = fetch_agenda(self._backend.build_client(), now, days, self._backend.zone)
        return agenda_payload(events, now, skipped, is_detailed=True)

    def create(self, new: NewEvent) -> WriteResult:
        """Add an event (no approval: it's new and marked as the tool's own)."""
        return self._write(lambda changes: changes.create(new))

    def update(self, ref: EventRef, edit: EventEdit) -> WriteResult:
        """Change an event (asks the owner first unless the tool made it)."""
        return self._write(lambda changes: changes.update(ref, edit))

    def delete(self, ref: EventRef) -> WriteResult:
        """Delete an event (asks the owner first unless the tool made it)."""
        return self._write(lambda changes: changes.delete(ref))

    def respond(self, ref: EventRef, response: str) -> WriteResult:
        """Answer an invitation (always someone else's event, so it asks unless turned off)."""
        return self._write(lambda changes: changes.respond(ref, response))

    def _write(self, operation: Callable[[EventChanges], AgendaEvent | None]) -> WriteResult:
        """Run one write, then refresh the agenda cache.

        Raises:
            CalendarError: The write failed or was refused; the cache isn't touched then.
        """
        backend = self._backend
        client = backend.build_client()
        event = operation(EventChanges(client, backend.build_gate(), backend.zone))
        now = datetime.now(backend.zone).astimezone(backend.zone)
        is_refreshed = refresh_cache(client, backend.cache_path, backend.status_path, now)
        return WriteResult(event, is_refreshed)
