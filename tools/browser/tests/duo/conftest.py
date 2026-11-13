"""Duo test fixtures: a stand-in for the audiohub voice hub, so no test reaches the real one."""

import asyncio
import json

import pytest
import pytest_asyncio
from support.fake_duo import HUB_OK_REPLY, HUB_TOKEN

from browser_tool.config import DuoSettings


@pytest.fixture
def hub_reply() -> bytes:
    """The fake hub's reply line; a test parametrizes `hub_reply` to change it."""
    return HUB_OK_REPLY


@pytest.fixture
def hub_rings_through() -> bool:
    """True makes the fake hub speak ring_through notes whatever `hub_reply` says."""
    return False


@pytest_asyncio.fixture
async def fake_hub(tmp_path, hub_reply, hub_rings_through):
    """A stand-in for the audiohub kernel: yields (DuoSettings aimed at it, received notes).

    It answers every note with `hub_reply`, except that with `hub_rings_through`
    a ring_through note gets HUB_OK_REPLY, as audiohub does while the owner is
    asleep or away. Its token file is a temp file holding HUB_TOKEN; the real
    hub's token is never read.
    """
    received: list[dict] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        note = json.loads(await reader.readline())
        received.append(note)
        rings = hub_rings_through and note.get("ring_through") is True
        writer.write(HUB_OK_REPLY if rings else hub_reply)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    token_file = tmp_path / "hub-token"
    token_file.write_text(HUB_TOKEN, encoding="ascii")
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield DuoSettings(hub_port=port, hub_token_file=str(token_file)), received
