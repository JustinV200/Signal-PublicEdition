"""A fake Claude Code inbox on a throwaway named pipe, for tests of anything that sends to one.

Tests here and in the tools that send to the orchestrator (the voice hub)
use it, so no test ever writes to a real session's inbox. Windows only, like
send_to_inbox.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

# Each fake gets its own pipe name, so parallel or leftover servers can't collide.
FAKE_PIPE_PREFIX = r"\\.\pipe\signal-orchestrator-test-"


@dataclass
class FakeInbox:
    """A running fake inbox.

    Attributes:
        address: Its named pipe, to put in a Claim.
        received: Every byte a sender wrote to it.
    """

    address: str
    received: bytearray = field(default_factory=bytearray)

    def frames(self) -> list[dict[str, Any]]:
        """The received lines, each parsed as JSON (auth line first)."""
        return [json.loads(line) for line in self.received.decode("utf-8").splitlines()]


def unused_pipe_address() -> str:
    """A fresh pipe name nothing serves, for a fake inbox or for the "pipe won't open" case."""
    return f"{FAKE_PIPE_PREFIX}{uuid.uuid4().hex}"


class _ReadingInbox(asyncio.Protocol):
    """Like Claude Code's inbox: reads lines, sends nothing back."""

    def __init__(self, received: bytearray) -> None:
        self._received = received

    def data_received(self, data: bytes) -> None:
        self._received.extend(data)


class _RefusingInbox(asyncio.Protocol):
    """Like Claude Code after a bad auth line: closes the connection."""

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        transport.close()


@asynccontextmanager
async def fake_inbox(*, is_refusing: bool = False) -> AsyncIterator[FakeInbox]:
    """Serve a fake inbox for the `async with` block.

    Args:
        is_refusing: Close every connection at once, as Claude Code does for a wrong token.

    Yields:
        The FakeInbox; read `received` or `frames()` after the send returns.
    """
    inbox = FakeInbox(unused_pipe_address())

    def make_protocol() -> asyncio.Protocol:
        return _RefusingInbox() if is_refusing else _ReadingInbox(inbox.received)

    loop = asyncio.get_running_loop()
    servers = await loop.start_serving_pipe(make_protocol, inbox.address)  # type: ignore[attr-defined]
    try:
        yield inbox
    finally:
        for server in servers:
            server.close()
