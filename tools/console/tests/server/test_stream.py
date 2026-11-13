"""GET /api/events over a plain streaming request with the token header: state, then history."""

import asyncio
import json

from signal_console.orchestrator import Claim, write_claim
from signal_console.server import SESSION_TOKEN_HEADER


async def _read_event(stream) -> tuple[str, dict]:
    name = None
    while True:
        line = (await asyncio.wait_for(stream.content.readline(), 2)).decode().rstrip("\n")
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: ") and name is not None:
            return name, json.loads(line.removeprefix("data: "))


async def test_stream_replays_each_message_with_its_delivery(console):
    write_claim(console.state_dir, Claim(r"\\.\pipe\x", "tok", None, ""))
    queue = console.services.events.subscribe()
    sent = await console.client.post(
        "/api/send", json={"text": "status?"}, headers=console.page_headers()
    )
    message_id = (await sent.json())["id"]
    while (await asyncio.wait_for(queue.get(), 2))[0] != "delivery":
        pass  # wait until the background delivery has been published

    # A page reload: a new stream gets a fresh state and tasks, then the kept history.
    headers = {SESSION_TOKEN_HEADER: console.token}
    async with console.client.get("/api/events", headers=headers) as stream:
        assert stream.headers["Content-Type"] == "text/event-stream"
        events = [await _read_event(stream) for _ in range(4)]

    assert [name for name, _ in events] == ["state", "tasks", "message", "delivery"]
    assert events[2][1]["id"] == events[3][1]["messageId"] == message_id
    assert events[3][1]["status"] == "sent"
