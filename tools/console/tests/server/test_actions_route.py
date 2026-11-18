"""POST /api/action runs the button in the server (never via the orchestrator) and reports it."""

import asyncio
import threading

import pytest

from signal_console.actions import StepFailed
from signal_console.hub import HubError


async def _events_until_settled(queue, message_id):
    """The action's message and delivery events, up to its final done or failed."""
    seen = []
    while True:
        name, data = await asyncio.wait_for(queue.get(), 2)
        if name in ("message", "delivery"):
            seen.append((name, data))
        is_ours = name == "delivery" and data["messageId"] == message_id
        if is_ours and data["status"] in ("done", "failed"):
            return seen


async def _post(console, action, args=None):
    body = {"action": action, **({"args": args} if args else {})}
    return await console.client.post("/api/action", json=body, headers=console.page_headers())


@pytest.mark.parametrize(
    ("action", "args", "call", "result"),
    [
        ("voice.start", None, ("hub", "start"), "Voice is running."),
        ("voice.stop", None, ("hub", "stop"), "Voice stopped."),
        (
            "board.load",
            {"name": "lecture"},
            ("whiteboard", "load", "--no-ink", "--", "lecture"),
            'Sent "lecture" to the projector.',
        ),
        (
            "board.realign",
            None,
            ("whiteboard", "realign"),
            "Realign finished. calibrated: reprojection error 0.4 px",
        ),
    ],
)
async def test_action_runs_directly(console, action, args, call, result):
    queue = console.services.events.subscribe()
    response = await _post(console, action, args)
    assert response.status == 202
    message_id = (await response.json())["id"]

    seen = await _events_until_settled(queue, message_id)
    assert seen[0][1]["id"] == message_id and seen[0][1]["kind"] == "action"
    assert [data["status"] for name, data in seen if name == "delivery"] == ["running", "done"]
    assert seen[-1][1]["result"] == result
    assert console.tools.calls == [call]
    assert console.inbox.sent == []  # the orchestrator is never asked
    # A board action forces a fresh whiteboard read (the throttled refresh may skip it).
    assert (console.status.board_reads > 0) == (call[0] == "whiteboard")


@pytest.mark.parametrize(
    ("action", "error", "shown"),
    [
        ("voice.start", HubError("Voice is already running."), "Voice is already running."),
        (
            "board.todo",
            StepFailed("whiteboard: error: night view is on"),
            "whiteboard: error: night view is on",
        ),
        # An OSError's local path stays in the server's log, never in Chat.
        (
            "voice.stop",
            OSError(13, "Access is denied", "C:/Users/owner/hub"),
            "Couldn't stop Voice (Access is denied). Try Stop voice again.",
        ),
    ],
)
async def test_action_failure_is_shown(console, action, error, shown):
    console.tools.error = error
    queue = console.services.events.subscribe()
    message_id = (await (await _post(console, action)).json())["id"]

    final = (await _events_until_settled(queue, message_id))[-1][1]
    assert final["status"] == "failed" and final["error"] == shown


async def test_double_click_is_refused_while_running(console):
    console.tools.gate = asyncio.Event()
    queue = console.services.events.subscribe()
    first = await _post(console, "board.calibrate")
    second = await _post(console, "board.calibrate")
    other_board = await _post(console, "board.realign")
    assert (first.status, second.status, other_board.status) == (202, 409, 409)

    console.tools.gate.set()
    await _events_until_settled(queue, (await first.json())["id"])
    assert console.tools.calls == [("whiteboard", "calibrate")]
    assert (await _post(console, "board.realign")).status == 202  # free again


async def test_stop_works_while_a_started_hub_loads(console):
    console.tools.hub_ready = threading.Event()
    console.tools.hub_stopped = threading.Event()
    queue = console.services.events.subscribe()
    start = await _post(console, "voice.start")
    await asyncio.to_thread(console.tools.hub_waiting.wait, 2)

    stop = await _post(console, "voice.stop")
    assert (start.status, stop.status) == (202, 202)
    # Start settles while Stop still runs: Stop's lock must survive Start's cleanup.
    console.tools.hub_ready.set()
    await _events_until_settled(queue, (await start.json())["id"])
    assert (await _post(console, "voice.start")).status == 409

    console.tools.hub_stopped.set()
    await _events_until_settled(queue, (await stop.json())["id"])
    assert console.tools.calls == [("hub", "start"), ("hub", "stop")]


async def test_stale_save_is_refused_before_running(console):
    response = await _post(console, "board.load", {"name": "deleted yesterday"})
    assert response.status == 400
    assert console.tools.calls == []
