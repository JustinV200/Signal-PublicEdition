"""End-to-end IPC tests: a real KernelServer on an ephemeral loopback port.

The blocking client runs in a worker thread (asyncio.to_thread) so the server
can answer on the test's event loop. Every server writes its token to a temp
file, so a real hub's token is never touched.
"""

import asyncio
import contextlib
import json
import socket
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio

from audiohub.kernel import (
    Dispatcher,
    HubNotRunningError,
    Kernel,
    KernelServer,
    NotificationDroppedError,
    NotificationRejectedError,
    PresenceFiles,
    send_notification,
)
from audiohub.kernel.ipc import MAX_LINE_BYTES
from audiohub.kernel.ipc import server as server_module

pytestmark = pytest.mark.asyncio
HOST = "127.0.0.1"


@dataclass
class Hub:
    kernel: Kernel
    port: int
    token_path: Path

    def line(self, **fields) -> bytes:
        """A request line carrying this hub's token plus `fields`."""
        payload = {"token": self.token_path.read_text(), **fields}
        return json.dumps(payload).encode() + b"\n"

    async def notify(self, source: str, text: str, priority: str = "normal") -> str:
        """Call the blocking client from a worker thread."""
        return await asyncio.to_thread(
            send_notification, HOST, self.port, source, text, priority, token_path=self.token_path
        )


@pytest_asyncio.fixture
async def hub(kernel_settings, fake_backend, tmp_path):
    kernel = Kernel(kernel_settings, Dispatcher(kernel_settings, backend=fake_backend))
    token_path = tmp_path / "ipc-token"
    async with KernelServer(kernel, HOST, 0, token_path) as server:
        yield Hub(kernel, server.port, token_path)


async def raw_exchange(port: int, payload: bytes) -> tuple[dict, bytes]:
    """Send raw bytes; return the first reply line (decoded) and whatever followed it."""
    reader, writer = await asyncio.open_connection(HOST, port)
    writer.write(payload)
    await writer.drain()
    reply = json.loads(await reader.readline())
    try:
        rest = await asyncio.wait_for(reader.read(), 2.0)  # b"" once the server hangs up
    except ConnectionResetError:
        # Hanging up with our unread bytes still queued makes Windows send a
        # reset instead of EOF; either way the server closed the connection.
        rest = b""
    writer.close()
    with contextlib.suppress(ConnectionResetError):  # already reset, see above
        await writer.wait_closed()
    return reply, rest


async def test_notification_reaches_the_kernel(hub) -> None:
    message_id = await hub.notify("build-agent", "Tests passed.", "high")
    assert await hub.kernel.wait_for_work(timeout_s=2.0)
    [(message, spoken)] = await hub.kernel.next_batch()
    assert (message.id, message.source, message.priority) == (message_id, "build-agent", "high")
    assert spoken == "Tests passed."


@pytest.mark.parametrize("token", [None, "not-the-token"], ids=["missing", "wrong"])
async def test_bad_or_missing_token_is_rejected_and_closes_the_connection(hub, token) -> None:
    fields = {"source": "a", "text": "hi"} | ({"token": token} if token else {})
    forged = json.dumps(fields).encode() + b"\n"
    reply, rest = await raw_exchange(hub.port, forged + hub.line(source="a", text="valid"))
    assert reply == {"ok": False, "error": "missing or invalid token"}
    assert rest == b""  # closed before the valid second line was read
    assert hub.kernel.pending_count == 0


async def test_http_wrapped_body_is_never_processed(hub) -> None:
    # What a web page's fetch() POST looks like on the wire, even with the token.
    body = hub.line(source="web-page", text="Say something embarrassing.")
    http = (
        b"POST / HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nContent-Type: text/plain\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    )
    reply, rest = await raw_exchange(hub.port, http)
    assert reply["ok"] is False and rest == b""
    assert hub.kernel.pending_count == 0


async def test_token_file_exists_only_while_the_hub_runs_and_a_restart_is_followed(
    kernel_settings, tmp_path
) -> None:
    token_path = tmp_path / "ipc-token"
    async with KernelServer(Kernel(kernel_settings), HOST, 0, token_path) as server:
        old_token = token_path.read_text()
        assert len(old_token) >= 32
        port = server.port
    assert not token_path.exists()
    with pytest.raises(HubNotRunningError, match="no IPC token"):
        await asyncio.to_thread(send_notification, HOST, port, "a", "hi", token_path=token_path)
    # A restarted hub has a new token; the client reads it at each call, never a cached one.
    async with KernelServer(Kernel(kernel_settings), HOST, 0, token_path) as server:
        assert token_path.read_text() != old_token
        args = (HOST, server.port, "a", "hi")
        assert await asyncio.to_thread(send_notification, *args, token_path=token_path)


@pytest_asyncio.fixture
async def asleep_hub(kernel_settings, fake_backend, tmp_path):
    """A hub whose presence files say the owner is asleep."""
    sleep_state = tmp_path / "state.json"
    sleep_state.write_text('{"is_asleep": true}')
    presence = PresenceFiles(sleep_state, tmp_path / "missing-away.json")
    kernel = Kernel(kernel_settings, Dispatcher(kernel_settings, backend=fake_backend))
    token_path = tmp_path / "ipc-token"
    async with KernelServer(kernel, HOST, 0, token_path, presence=presence) as server:
        yield Hub(kernel, server.port, token_path)


async def test_notification_is_dropped_while_owner_is_asleep(asleep_hub) -> None:
    with pytest.raises(NotificationDroppedError, match="dropped: the owner is asleep"):
        await asleep_hub.notify("a", "hi")
    assert asleep_hub.kernel.pending_count == 0


@pytest.mark.parametrize(
    ("priority", "is_spoken"),
    [("urgent", True), ("high", False)],
    ids=["urgent-rings-through", "non-urgent-refused"],
)
async def test_ring_through_while_asleep_needs_urgent(asleep_hub, priority, is_spoken) -> None:
    line = asleep_hub.line(source="browser", text="Duo", priority=priority, ring_through=True)
    reader, writer = await asyncio.open_connection(HOST, asleep_hub.port)
    writer.write(line)
    await writer.drain()
    reply = json.loads(await reader.readline())
    writer.close()
    assert reply["ok"] is is_spoken and "dropped" not in reply
    assert asleep_hub.kernel.pending_count == (1 if is_spoken else 0)


async def test_invalid_request_gets_an_error_reply(hub) -> None:
    reply, _ = await raw_exchange(hub.port, hub.line(source="a", text="hi", priority="meh"))
    assert reply["ok"] is False and "priority" in reply["error"]


async def test_oversized_line_gets_an_error_reply(hub) -> None:
    reply, _ = await raw_exchange(hub.port, b"x" * (MAX_LINE_BYTES * 2) + b"\n")
    assert reply == {"ok": False, "error": f"line is longer than {MAX_LINE_BYTES} bytes"}


async def test_deeply_nested_json_gets_an_error_reply(hub) -> None:
    reply, _ = await raw_exchange(hub.port, b"[" * 5000 + b"]" * 5000 + b"\n")
    assert reply["ok"] is False and "JSON" in reply["error"]


async def test_several_requests_share_one_connection(hub) -> None:
    reader, writer = await asyncio.open_connection(HOST, hub.port)
    writer.write(hub.line(source="a", text="one") + hub.line(source="a", text="two"))
    await writer.drain()
    replies = [json.loads(await reader.readline()) for _ in range(2)]
    writer.close()
    await writer.wait_closed()
    assert all(r["ok"] for r in replies) and replies[0]["id"] != replies[1]["id"]
    assert hub.kernel.pending_count == 2


async def test_ipc_cannot_mark_a_notification_as_a_direct_reply(hub) -> None:
    reply, _ = await raw_exchange(hub.port, hub.line(source="a", text="hi", is_direct_reply=True))
    assert reply["ok"] is False
    await hub.notify("a", "hi")
    assert await hub.kernel.wait_for_work(timeout_s=2.0)
    [(message, _)] = await hub.kernel.next_batch()
    assert message.is_direct_reply is False


@pytest.mark.parametrize("host", ["0.0.0.0", "::1", "localhost", "192.168.1.5"])
async def test_server_refuses_non_loopback_hosts(kernel_settings, host) -> None:
    with pytest.raises(ValueError, match="loopback"):
        KernelServer(Kernel(kernel_settings), host, 0)


async def test_client_reports_a_hub_that_is_not_running(tmp_path) -> None:
    token_path = tmp_path / "ipc-token"
    token_path.write_text("stale-token")  # left behind by a crashed hub
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        free_port = probe.getsockname()[1]
    with pytest.raises(HubNotRunningError, match="isn't running"):
        await asyncio.to_thread(
            send_notification, HOST, free_port, "a", "hi", token_path=token_path
        )


async def test_client_raises_when_the_hub_rejects(tmp_path) -> None:
    async def reject(reader, writer) -> None:
        await reader.readline()
        writer.write(b'{"ok": false, "error": "kernel is shutting down"}\n')
        await writer.drain()
        writer.close()

    token_path = tmp_path / "ipc-token"
    token_path.write_text("any-token")
    server = await asyncio.start_server(reject, HOST, 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        with pytest.raises(NotificationRejectedError, match="shutting down"):
            await asyncio.to_thread(send_notification, HOST, port, "a", "hi", token_path=token_path)


async def test_connections_over_the_cap_are_refused(hub, monkeypatch) -> None:
    monkeypatch.setattr(server_module, "MAX_CONNECTIONS", 2)
    open_connections = []
    for _ in range(2):
        reader, writer = await asyncio.open_connection(HOST, hub.port)
        writer.write(hub.line(source="a", text="hi"))
        assert json.loads(await reader.readline())["ok"]  # the handler is registered now
        open_connections.append(writer)
    reply, _ = await raw_exchange(hub.port, hub.line(source="a", text="hi"))
    assert reply == {"ok": False, "error": server_module.TOO_MANY_CONNECTIONS}
    for writer in open_connections:
        writer.close()


async def test_close_does_not_wait_for_idle_connections(kernel_settings, tmp_path) -> None:
    token_path = tmp_path / "ipc-token"
    server = KernelServer(Kernel(kernel_settings), HOST, 0, token_path)
    await server.start()
    reader, writer = await asyncio.open_connection(HOST, server.port)
    writer.write(
        json.dumps({"token": token_path.read_text(), "source": "a", "text": "hi"}).encode()
    )
    writer.write(b"\n")
    await reader.readline()
    loop = asyncio.get_running_loop()
    started = loop.time()
    await server.close()
    assert loop.time() - started < server_module.CLOSE_TIMEOUT_S
    writer.close()
