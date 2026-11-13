"""Tests for send_to_hub's wire format, against a fake hub on a loopback port."""

import asyncio
import json

import pytest

from signal_hub_notify import HubDroppedError, HubNote, HubRejectedError, send_to_hub


async def _serve_once(reply: bytes, received: list[dict]) -> asyncio.Server:
    """A fake hub that records one request line and answers with `reply`."""

    async def fake_hub(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        received.append(json.loads(await reader.readline()))
        writer.write(reply)
        await writer.drain()
        writer.close()

    return await asyncio.start_server(fake_hub, "127.0.0.1", 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("note", "extra_fields"),
    [
        (HubNote("session:Signal", "Done.", "low"), {}),
        # ring_through goes on the wire only when set.
        (HubNote("session:Signal", "Done.", "urgent", ring_through=True), {"ring_through": True}),
    ],
    ids=["plain", "ring-through"],
)
async def test_sends_one_json_line_and_returns_the_hub_id(note: HubNote, extra_fields) -> None:
    received: list[dict] = []
    server = await _serve_once(b'{"ok": true, "id": "m7"}\n', received)
    port = server.sockets[0].getsockname()[1]
    async with server:
        message_id = await send_to_hub("127.0.0.1", port, note, "hub-secret")

    assert message_id == "m7"
    base = {"source": "session:Signal", "text": "Done.", "token": "hub-secret"}
    assert received == [{**base, "priority": note.priority, **extra_fields}]


DROPPED_ASLEEP = b'{"ok": false, "error": "dropped: the owner is asleep", "dropped": true}\n'
DROPPED_UNLISTED = b'{"ok": false, "error": "dropped: <b>call me</b>", "dropped": true}\n'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "dropped_reason"),
    [
        (b'{"ok": false, "error": "bad token"}\n', None),
        (DROPPED_ASLEEP, "the owner is asleep"),
        # A drop reason outside the allowlist is never passed on: a plain refusal.
        (DROPPED_UNLISTED, None),
    ],
    ids=["refused", "dropped", "unlisted-drop-reason"],
)
async def test_a_refusal_raises_hub_rejected_and_a_drop_names_its_reason(
    reply: bytes, dropped_reason: str | None
) -> None:
    server = await _serve_once(reply, [])
    port = server.sockets[0].getsockname()[1]
    async with server:
        with pytest.raises(HubRejectedError) as raised:
            await send_to_hub("127.0.0.1", port, HubNote("browser", "Hi."), "token")
    is_dropped = isinstance(raised.value, HubDroppedError)
    assert (raised.value.reason if is_dropped else None) == dropped_reason
