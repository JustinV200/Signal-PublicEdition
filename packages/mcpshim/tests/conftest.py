"""Fixtures for the shim tests: a fake client driving a Shim around tests/fake_server.py."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from signal_mcpshim import Shim, ShimTimings

FAKE_SERVER = str(Path(__file__).with_name("fake_server.py"))
FAST = ShimTimings(
    first_respawn_delay=0.01, max_respawn_delay=0.05, ready_timeout=5, shutdown_grace=2
)
REPLY_TIMEOUT = 10


class FakeClient:
    """Plays Claude Code: sends JSON-RPC lines into the shim and reads what comes back."""

    def __init__(self, *server_args: str, timings: ShimTimings = FAST) -> None:
        self.received: asyncio.Queue[dict] = asyncio.Queue()
        command = [sys.executable, FAKE_SERVER, *server_args]
        self.shim = Shim(command, lambda line: self.received.put_nowait(json.loads(line)), timings)
        self.task = asyncio.create_task(self.shim.run())

    def send(self, request_id, method, params=None) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if request_id is not None:
            message["id"] = request_id
        self.shim.feed_client_line(json.dumps(message).encode())

    def call_tool(self, request_id, name: str) -> None:
        self.send(request_id, "tools/call", {"name": name, "arguments": {}})

    async def receive(self) -> dict:
        return await asyncio.wait_for(self.received.get(), REPLY_TIMEOUT)

    async def handshake(self) -> dict:
        """Run initialize + initialized like Claude Code; return the initialize reply."""
        self.send(0, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
        reply = await self.receive()
        self.send(None, "notifications/initialized")
        return reply

    async def close(self) -> None:
        self.shim.feed_client_line(None)
        await asyncio.wait_for(self.task, REPLY_TIMEOUT)


@pytest.fixture
async def client():
    fake = FakeClient()
    yield fake
    await fake.close()


@pytest.fixture
async def crash_looping_client():
    """A client whose server exits at startup, every time."""
    fake = FakeClient("--crash", timings=ShimTimings(first_respawn_delay=0.01, ready_timeout=0.5))
    yield fake
    await fake.close()
