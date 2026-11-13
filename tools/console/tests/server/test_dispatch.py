"""POST /api/send: a "you" message at once, then one delivery result naming that message."""

import asyncio

import pytest

from signal_console.orchestrator import Claim, write_claim


async def _next_event(queue, name):
    while True:
        event_name, data = await asyncio.wait_for(queue.get(), 2)
        if event_name == name:
            return data


@pytest.mark.parametrize("inbox", ["takes it", "unclaimed", "breaks"])
async def test_send_shows_message_then_delivery(console, inbox):
    if inbox != "unclaimed":
        write_claim(console.state_dir, Claim(r"\\.\pipe\x", "tok", None, ""))
    if inbox == "breaks":
        console.inbox.error = RuntimeError("internal detail")
    queue = console.services.events.subscribe()

    response = await console.client.post(
        "/api/send", json={"text": "status?"}, headers=console.page_headers()
    )
    message_id = (await response.json())["id"]

    message = await _next_event(queue, "message")
    assert (message["id"], message["role"], message["text"]) == (message_id, "you", "status?")
    delivery = await _next_event(queue, "delivery")
    assert delivery["messageId"] == message_id
    assert delivery["id"] != message_id  # ids are unique across event types
    if inbox == "takes it":
        assert delivery["status"] == "sent"
        assert [text for _, text in console.inbox.sent] == ["[Signal console] the owner: status?"]
    elif inbox == "unclaimed":
        assert delivery["status"] == "failed" and "console claim" in delivery["error"]
    else:
        assert delivery["status"] == "failed" and "internal detail" not in delivery["error"]
