"""The guest relay checks the token on every connection (a security boundary).

relay.py is stdlib-only guest code (tools/browser/docker/guest), loaded here
from its file and served on the host's loopback in front of a fake Edge.
"""

import asyncio
import importlib.util
from pathlib import Path

import pytest

RELAY_PATH = Path(__file__).resolve().parents[3] / "docker" / "guest" / "relay.py"
TOKEN = "t" * 43
LOOPBACK = "127.0.0.1"
EDGE_REPLY = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
REPLY_TIMEOUT_S = 7.0


def _load_relay():
    spec = importlib.util.spec_from_file_location("guest_relay", RELAY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relay = _load_relay()


def request(*headers: str, method: str = "GET") -> bytes:
    lines = [f"{method} /json/version HTTP/1.1", "Host: 127.0.0.1", *headers, "", ""]
    return "\r\n".join(lines).encode()


GOOD = request(f"Authorization: Bearer {TOKEN}")
BAD_REQUESTS = {
    "no token": request(),
    "wrong token": request("Authorization: Bearer " + "x" * len(TOKEN)),
    "Basic scheme": request(f"Authorization: Basic {TOKEN}"),
    "two Authorization headers": request(f"Authorization: Bearer {TOKEN}", "Authorization: x"),
    "POST with the token": request(f"Authorization: Bearer {TOKEN}", method="POST"),
    "binary garbage": b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03\r\n\r\n",
}


class FakeEdge:
    """Stands in for Edge's CDP port: records each request head, answers 200."""

    def __init__(self) -> None:
        self.received = b""

    async def start(self) -> asyncio.Server:
        return await asyncio.start_server(self._serve, LOOPBACK, 0)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.received += await reader.readuntil(b"\r\n\r\n")
        writer.write(EDGE_REPLY)
        await writer.drain()
        await reader.read()  # hold the connection until the client leaves
        writer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_request", BAD_REQUESTS.values(), ids=BAD_REQUESTS.keys())
async def test_each_connection_needs_the_token(bad_request):
    edge = FakeEdge()
    edge_server = await edge.start()
    upstream = edge_server.sockets[0].getsockname()[:2]
    server = await relay.serve(
        TOKEN, relay.ConnectionTracker(), listen=(LOOPBACK, 0), upstream=upstream
    )
    port = server.sockets[0].getsockname()[1]
    async with edge_server, server:
        # An authenticated connection is let through and stays open...
        good_reader, good_writer = await asyncio.open_connection(LOOPBACK, port)
        good_writer.write(GOOD)
        assert await good_reader.readuntil(b"\r\n\r\n") == EDGE_REPLY
        # ...yet a new connection without a valid token is still refused and closed.
        reader, writer = await asyncio.open_connection(LOOPBACK, port)
        writer.write(bad_request)
        reply = await asyncio.wait_for(reader.read(), REPLY_TIMEOUT_S)
        writer.close()
        good_writer.close()
    assert reply.startswith(b"HTTP/1.1 401")
    # Edge saw only the good request, with the token stripped.
    assert edge.received.count(b"GET /json/version") == 1
    assert TOKEN.encode() not in edge.received
