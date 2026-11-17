"""Security table for the daemon HTTP server: loopback only, token, bad requests dropped."""

import asyncio
import json

import pytest

from analysis_chamber.daemon import DaemonClient, start_daemon

GOOD_BODY = b"{}"


def _post(token: str, body: bytes = GOOD_BODY, path: str = "/list") -> bytes:
    head = (
        f"POST {path} HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer {token}\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    )
    return head.encode() + body


# Each request must get no reply at all: the server just closes the connection.
BAD_REQUESTS = {
    "no token": b"POST /list HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}",
    "wrong token": _post("not-the-token"),
    "get request": b"GET / HTTP/1.1\r\nHost: x\r\n\r\n",
    "garbage": b"\x16\x03\x01 hello\r\n\r\n",
    "oversized body": _post("{token}", b"{}", "/list").replace(b"Length: 2", b"Length: 9999999"),
    "body not json": _post("{token}", b"{nope"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(BAD_REQUESTS))
async def test_bad_request_closes_connection(daemon, name: str) -> None:
    raw = BAD_REQUESTS[name].replace(b"{token}", daemon.token.encode())
    reader, writer = await asyncio.open_connection("127.0.0.1", daemon.port)
    writer.write(raw)
    await writer.drain()
    assert await asyncio.wait_for(reader.read(), 5) == b""
    writer.close()


@pytest.mark.asyncio
async def test_loopback_only_token_works_and_one_daemon_per_state_dir(
    daemon, config, phases
) -> None:
    hosts = {sock.getsockname()[0] for sock in daemon.api.server.sockets}
    assert hosts == {"127.0.0.1"}
    state = json.loads((config.state_dir / "daemon.json").read_text())
    assert state["port"] == daemon.port and state["token"] == daemon.token
    reply = await asyncio.to_thread(DaemonClient(config.state_dir).list)
    assert reply == {"runs": []}
    with pytest.raises(RuntimeError, match="already running"):
        await start_daemon(config, phases.backend())
