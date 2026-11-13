"""A daemon harness for the lifecycle tests: real manager, store and IPC server; fake SDK and hub.

The server listens on an ephemeral loopback port and tests talk to it with
the real ipc client, so requests go through the full wire protocol.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from signal_hub_notify import Notifier
from support.fakes import FakeApprover, FakeClientFactory, RecordingHub, reply_with_echo

from claude_sessions.daemon import (
    DaemonServer,
    ListenSpec,
    ManagerDeps,
    SessionManager,
    SessionStore,
)
from claude_sessions.ipc import DaemonEndpoint, call_daemon
from claude_sessions.tokens import read_token

HOST = "127.0.0.1"
# request_line's default: use the token the running daemon wrote.
DAEMON_TOKEN = object()
STATE_TIMEOUT_S = 5.0
POLL_S = 0.01


class DaemonHarness:
    """One in-process daemon plus handles on its fakes."""

    def __init__(self, state_dir: Path, repo_root: Path) -> None:
        self.factory = FakeClientFactory(reply_with_echo)
        self.approver = FakeApprover()
        self.hub = RecordingHub()
        self.transcript_cwds: dict[str, Path] = {}
        self.repo_root = repo_root
        self.token_file = state_dir / "token"
        self.token = ""
        hub_token_file = state_dir / "hub-token"
        hub_token_file.parent.mkdir(parents=True)
        hub_token_file.write_text("test-hub-token", encoding="ascii")
        self._notifier = Notifier(HOST, 1, hub_token_file, send=self.hub)
        self._store = SessionStore(state_dir / "sessions.json")
        self.manager: SessionManager | None = None
        self.server: DaemonServer | None = None

    async def start(self) -> None:
        """Load the store into a fresh manager and serve it."""
        deps = ManagerDeps(
            store=self._store,
            client_factory=self.factory,
            approver=self.approver,
            notifier=self._notifier,
            find_transcript_cwd=self.transcript_cwds.get,
            clock=time.time,
            repo_roots=(self.repo_root,),
        )
        self.manager = SessionManager(deps)
        self.manager.load()
        self.server = DaemonServer(
            self.manager, ListenSpec(HOST, 0, self.token_file), on_shutdown=lambda: None
        )
        await self.server.start()
        # Read back like a real client, so the test sees what the server published.
        self.token = read_token(self.token_file)

    def rival_server(self) -> DaemonServer:
        """A second daemon aimed at the same port and token file as the running one."""
        return DaemonServer(
            self.manager, ListenSpec(HOST, self.server.port, self.token_file), lambda: None
        )

    async def crash_and_restart(self) -> None:
        """Replace the daemon without stopping its sessions, as after a crash."""
        await self.server.close()
        await self.start()

    async def close(self) -> None:
        await self.manager.stop_all()
        await self.server.close()
        await self._notifier.drain()

    async def call(self, op: str, **args: Any) -> Any:
        return await call_daemon(DaemonEndpoint(HOST, self.server.port, self.token), op, args)

    async def raw(self, line: bytes) -> list[dict[str, Any]]:
        """Send bytes that skip client validation; return all replies until the daemon hangs up."""
        reader, writer = await asyncio.open_connection(HOST, self.server.port)
        try:
            writer.write(line)
            await writer.drain()
            writer.write_eof()
            return [json.loads(reply) for reply in (await reader.read()).splitlines()]
        finally:
            writer.close()

    def request_line(
        self, op: str, args: dict[str, Any], token: str | None | object = DAEMON_TOKEN
    ) -> bytes:
        """A raw request line, with the daemon's token unless told otherwise (None: no token)."""
        payload: dict[str, Any] = {"op": op, "args": args}
        if token is DAEMON_TOKEN:
            token = self.token
        if token is not None:
            payload["token"] = token
        return json.dumps(payload).encode() + b"\n"

    async def wait_for_state(self, session_id: str, state: str) -> dict[str, Any]:
        """Poll status until the session reaches state; fail after STATE_TIMEOUT_S."""
        deadline = time.monotonic() + STATE_TIMEOUT_S
        while True:
            status = await self.call("status", id=session_id, last_n=10)
            if status["state"] == state:
                return status
            if time.monotonic() > deadline:
                pytest.fail(f"session never became {state}; last status {status}")
            await asyncio.sleep(POLL_S)

    async def drain_notes(self) -> list[str]:
        """Wait for posted notes and return their texts."""
        await self._notifier.drain()
        return [note.text for note in self.hub.notes]


@pytest_asyncio.fixture
async def daemon(tmp_path: Path):
    harness = DaemonHarness(tmp_path / ".state", repo_root=tmp_path)
    await harness.start()
    yield harness
    await harness.close()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    folder = tmp_path / "Demo"
    folder.mkdir()
    return folder
