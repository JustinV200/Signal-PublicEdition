"""Shared fixture: the console app on a real loopback test server, with fake status, inbox
and action tools (no real hub or whiteboard is ever touched)."""

import asyncio
import sys
import threading
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from signal_brief import BriefPaths

from signal_console.actions import ActionTools
from signal_console.health import HealthPaths
from signal_console.hub import HubRecord
from signal_console.models import ModelFiles
from signal_console.orchestrator import Claim, messages
from signal_console.server import (
    SESSION_TOKEN_HEADER,
    ActionRunner,
    Dispatcher,
    EventHub,
    Services,
    SessionAuth,
    build_app,
)
from signal_console.server.tasks_feed import TasksFeed
from signal_console.setup_cli import SetupRunner
from signal_console.status import DeviceReader
from signal_console.turns import TurnReport

LOCAL_KEY = "local-key-for-tests"
# A stand-in setup CLI: prints its arguments and stdin, exits with the code `exit=N` asks for.
FAKE_SETUP_CLI = Path(__file__).parent / "fakes" / "fake_setup_cli.py"


@dataclass
class FakeStatus:
    """Stands in for StatusWatcher: fixed state, one save, records turn reports."""

    saves_now: dict[str, str | None] = field(default_factory=lambda: {"lecture": None})
    turn_reports: list[TurnReport] = field(default_factory=list)
    board_reads: int = 0

    async def snapshot(self) -> dict[str, Any]:
        return {"orchestrator": {"claimed": False, "alive": False, "label": None, "turn": None}}

    async def saves(self) -> dict[str, str | None]:
        self.board_reads += 1
        return dict(self.saves_now)

    async def refresh(self, *, read_boards: bool) -> None:
        pass

    def voice_status(self) -> dict[str, Any]:
        return {"running": False, "phase": "off", "startedBy": None}

    def record_turn(self, report: TurnReport) -> None:
        self.turn_reports.append(report)


@dataclass
class FakeInbox:
    """Stands in for the orchestrator's inbox: records sends, or raises `error` if set."""

    sent: list[tuple[Claim, str]] = field(default_factory=list)
    error: Exception | None = None

    async def send(self, claim: Claim, text: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((claim, text))


@dataclass
class FakeTools:
    """Stands in for the hub and whiteboard CLI: records calls, raises `error` if set.

    `gate`, when set, holds every whiteboard command until a test sets it;
    `hub_ready`, when set, holds a voice start's wait (which sets `hub_waiting`) until set;
    `hub_stopped`, when set, holds a voice stop until set.
    """

    calls: list[tuple[str, ...]] = field(default_factory=list)
    error: Exception | None = None
    gate: asyncio.Event | None = None
    hub_ready: threading.Event | None = None
    hub_waiting: threading.Event = field(default_factory=threading.Event)
    hub_stopped: threading.Event | None = None

    def start_hub(self, state_dir: Path) -> HubRecord:
        self._record(("hub", "start"))
        return HubRecord(42, 1.0)

    def wait_for_hub(self, state_dir: Path, record: HubRecord) -> bool:
        self.hub_waiting.set()
        if self.hub_ready is not None:
            self.hub_ready.wait(2)
        return True

    def stop_hub(self, state_dir: Path) -> bool:
        if self.hub_stopped is not None:
            self.hub_stopped.wait(2)
        return self._record(("hub", "stop"))

    async def run_whiteboard(self, args: Sequence[str]) -> str:
        if self.gate is not None:
            await self.gate.wait()
        self._record(("whiteboard", *args))
        return "calibrated: reprojection error 0.4 px\nboard outline found"

    def as_tools(self) -> ActionTools:
        return ActionTools(self.start_hub, self.stop_hub, self.run_whiteboard, self.wait_for_hub)

    def _record(self, call: tuple[str, ...]) -> bool:
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        return True


@dataclass
class Console:
    """The running test app and what its fakes saw.

    The web folder is state_dir / "dist", empty until a test builds a frontend there,
    and the whiteboard's state folder is state_dir / "whiteboard" (empty: the daemon is off).
    """

    client: TestClient
    services: Services
    status: FakeStatus
    state_dir: Path
    inbox: FakeInbox
    token: str
    tools: FakeTools

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.client.port}"

    def page_headers(self) -> dict[str, str]:
        """What the logged-in page sends on a POST."""
        return {"Origin": self.origin, SESSION_TOKEN_HEADER: self.token}

    async def raw_request(
        self, method: str, target: str, extra_headers: bytes = b""
    ) -> tuple[int, bytes]:
        """Send one request byte for byte, for paths and headers the client would clean up.

        Returns:
            The status code and the body (read until the server closes).
        """
        reader, writer = await asyncio.open_connection("127.0.0.1", self.client.port)
        head = (
            f"{method} {target} HTTP/1.1\r\nHost: 127.0.0.1:{self.client.port}\r\n"
            "Connection: close\r\nContent-Length: 0\r\n"
        )
        writer.write(head.encode("latin-1") + extra_headers + b"\r\n")
        raw = await asyncio.wait_for(reader.read(), 2)
        writer.close()
        await writer.wait_closed()
        status_line, _, rest = raw.partition(b"\r\n")
        return int(status_line.split()[1]), rest.partition(b"\r\n\r\n")[2]


def tmp_model_files(folder: Path) -> ModelFiles:
    """The model strip's files under `folder`, never the repo's real settings."""
    return ModelFiles(
        settings=folder / "settings.local.json",
        backup=folder / "settings.local.bak.json",
        session_models=folder / "session-models.json",
        brain_choice=folder / "brain-choice.json",
        lock=folder / "models.lock",
    )


def tmp_health_paths(folder: Path) -> HealthPaths:
    """Every file the health checks read, under `folder`: never the real .state or settings."""
    return HealthPaths(
        state_dir=folder,
        web_dist_dir=folder / "dist",
        settings_files=(folder / "settings.json", folder / "settings.local.json"),
        edge_path=folder / "msedge.exe",
        whiteboard_dir=folder / "whiteboard",
        tool_root=folder / "console",
        # tcpmux, a port nothing on a Windows PC listens on: the port row reads "free".
        default_port=1,
    )


@pytest_asyncio.fixture
async def console(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Console]:
    # Never the repo's real .env: with no file there, the chat marker names "the owner".
    monkeypatch.setattr(messages, "ENV_FILE_PATH", tmp_path / ".env")
    events = EventHub(tmp_path / "history.jsonl")
    status = FakeStatus()
    inbox = FakeInbox()
    dispatcher = Dispatcher(events, tmp_path, inbox.send)
    tools = FakeTools()
    auth = SessionAuth()
    token = auth.log_in(auth.issue_login_key())
    assert token is not None
    async with aiohttp.ClientSession() as session:
        services = Services(
            events,
            auth,
            status,
            dispatcher,
            ActionRunner(events, tmp_path, status, tools.as_tools()),
            LOCAL_KEY,
            TasksFeed(events, tmp_path / "tasks.json", tmp_path / "usage.json"),
            DeviceReader(session, tmp_path / "whiteboard", tmp_path / "profile"),
            session,
            tmp_path / "whiteboard",
            BriefPaths(tmp_path / "brief", tmp_path / "sleep-state.json"),
            tmp_model_files(tmp_path / "models"),
            SetupRunner([sys.executable, str(FAKE_SETUP_CLI)], tmp_path),
            tmp_health_paths(tmp_path),
        )
        app = build_app(services, tmp_path / "dist")
        async with TestClient(TestServer(app, host="127.0.0.1")) as client:
            yield Console(client, services, status, tmp_path, inbox, token, tools)
