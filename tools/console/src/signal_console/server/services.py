"""What the routes work with, stored on the app under SERVICES_KEY."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import aiohttp
from aiohttp import web
from signal_brief import BriefPaths

from signal_console.models import ModelFiles
from signal_console.server.action_runner import ActionRunner
from signal_console.server.dispatch import Dispatcher
from signal_console.server.events import EventHub
from signal_console.server.security import SessionAuth
from signal_console.server.tasks_feed import TasksFeed
from signal_console.setup_cli import SetupRunner
from signal_console.status import DeviceReader
from signal_console.turns import TurnReport


class StatusSource(Protocol):
    """The live status the routes read (StatusWatcher; tests pass a fake)."""

    async def snapshot(self) -> dict[str, Any]:
        """The current /api/state body."""
        ...

    async def refresh(self, *, read_boards: bool) -> None:
        """Re-read the status now and publish `state` if it changed."""
        ...

    async def saves(self) -> dict[str, str | None]:
        """The whiteboard saves that exist right now, each name mapped to its refresher."""
        ...

    def voice_status(self) -> dict[str, Any]:
        """The voice hub's last polled state ({running, phase, startedBy}), without re-reading."""
        ...

    def record_turn(self, report: TurnReport) -> None:
        """Apply a turn hook report from the claimed orchestrator."""
        ...


@dataclass(frozen=True)
class Services:
    """The server's parts.

    Attributes:
        events: The SSE feed and its history.
        auth: Login keys and page session tokens.
        status: The orchestrator, voice and board status.
        dispatcher: Sends typed messages to the orchestrator.
        actions: Runs the page's buttons directly.
        local_key: The secret local callers send as X-Console-Key.
        tasks: The Tasks page's data (tasks.json and usage.json).
        devices: The Connected devices rows.
        session: The HTTP client for the whiteboard daemon (the camera proxy).
        whiteboard_dir: The whiteboard daemon's .state folder (its port and token).
        brief_paths: The brief's state files, for the Away/Here toggle.
        models: The model strip's files (settings, session models, voice's pick).
        setup: Runs the setup CLI for the Setup and Tools pages.
    """

    events: EventHub
    auth: SessionAuth
    status: StatusSource
    dispatcher: Dispatcher
    actions: ActionRunner
    local_key: str
    tasks: TasksFeed
    devices: DeviceReader
    session: aiohttp.ClientSession
    whiteboard_dir: Path
    brief_paths: BriefPaths
    models: ModelFiles
    setup: SetupRunner


SERVICES_KEY = web.AppKey("services", Services)
