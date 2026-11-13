"""What ClaudeBrain needs from its Claude Code session, and how it builds and hears from one.

SdkSession (brain/sdk_session.py) is the real session; tests inject a fake through
SessionFactory, so ClaudeBrain never touches the SDK itself.
"""

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Protocol

from audiohub.brain.events import SessionEvent
from audiohub.brain.handoff_tool import HandOff
from audiohub.brain.permissions import PermissionDecider
from audiohub.config import BrainSettings


class BrainSession(Protocol):
    """What ClaudeBrain needs from a session. SdkSession implements it."""

    @property
    def session_id(self) -> str | None:
        """The conversation's id once a turn has finished (for resume), else None."""
        ...

    async def connect(self, resume: str | None = None) -> None:
        """Open the session, carrying on conversation `resume` if given."""

    async def disconnect(self) -> None:
        """Close the session. Safe to call twice."""

    async def send(self, text: str) -> None:
        """Send one user message, starting a turn."""

    def events(self) -> AsyncIterator[SessionEvent]:
        """Yield every event of the session, across turns, until it ends."""

    async def interrupt(self) -> None:
        """Stop the running turn early."""

    async def set_model(self, model: str) -> None:
        """Switch the model from the next turn on, without reconnecting."""

    async def mcp_server_statuses(self) -> dict[str, str]:
        """Each MCP server's name and status ("connected", "pending", "failed", ...)."""
        ...

    async def reconnect_mcp_server(self, name: str) -> None:
        """Reconnect one MCP server; raises if that fails."""


SessionFactory = Callable[[BrainSettings, Path, PermissionDecider, HandOff], BrainSession]
"""Builds a session from the settings, cwd, the gate's decider and the hand-off tool's handler."""

ToolCallHandler = Callable[[str], None]
"""Told the name of each tool call the gate allows, e.g. "mcp__audiohub__music_pause"."""
