"""GET /api/events: the Server-Sent Events feed (state, tasks, message, delivery, voice, note).

Needs the X-Console-Token header like every page route, so the page reads it
with a streaming fetch() (EventSource can't send headers). The body is plain
text/event-stream: `event: <name>`, `data: <one-line JSON>`, a blank line, and
`: keepalive` comment lines while idle.

On connect it sends the current state and tasks, then replays the kept history
(message, delivery, voice and note events), then streams live events. It
subscribes before the replay, so nothing falls in the gap, but an event may
arrive twice.

Dedupe rule: every event except `state` has an `id` that is unique across all
event types and the same on every replay, so a client keeps the first event it
sees with a given id and drops repeats. `state` has no id; each one is a full
snapshot that replaces the last, and so is `tasks` (the Tasks page's data). A
`delivery` names its message in `messageId`. Its status is `sent` or `failed` for a
typed message, and `running`, then `done` (with `result`) or `failed` (with
`error`), for a button.
"""

import asyncio
import json
from typing import Any

from aiohttp import web

from signal_console.server.events import END_OF_STREAM
from signal_console.server.services import SERVICES_KEY

# A comment line this often keeps idle connections open and finds dead ones. The page
# reopens a stream that sends nothing for 20 s (web/src/api/events.ts STALL_MS), so this
# must stay well under that.
KEEPALIVE_S = 5.0


def add_stream_route(app: web.Application) -> None:
    """Register GET /api/events."""
    app.router.add_get("/api/events", events)


async def events(request: web.Request) -> web.StreamResponse:
    """Stream the console's events until the page goes away or the server stops."""
    services = request.app[SERVICES_KEY]
    response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
    await response.prepare(request)
    queue = services.events.subscribe()
    try:
        await _send(response, "state", await services.status.snapshot())
        await _send(response, "tasks", services.tasks.current())
        for name, data in services.events.history():
            await _send(response, name, data)
        await _stream(response, queue)
    except ConnectionResetError:
        pass  # The page closed the stream; nothing to clean up beyond unsubscribing.
    finally:
        services.events.unsubscribe(queue)
    return response


async def _stream(response: web.StreamResponse, queue: asyncio.Queue[Any]) -> None:
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
        except TimeoutError:
            await response.write(b": keepalive\n\n")
            continue
        if event == END_OF_STREAM:
            return
        await _send(response, *event)


async def _send(response: web.StreamResponse, name: str, data: dict[str, Any]) -> None:
    # json.dumps never emits a raw newline, so the data stays on one SSE line.
    await response.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
