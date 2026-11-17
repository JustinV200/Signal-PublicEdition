"""The daemon's HTTP/1.1 server: 127.0.0.1 only, one request per connection, JSON replies.

A malformed or unauthenticated request gets no reply at all; the connection is
just closed (coding rule 7). An authenticated request gets 200 with the result,
400 with {"error"} when the chamber refuses it (or the leak guard blocks it),
or 500 when something unexpected broke (logged with its traceback).
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from analysis_chamber.daemon.api.request import MAX_LINE_BYTES, BadRequest, read_request
from analysis_chamber.daemon.api.routes import dispatch
from analysis_chamber.daemon.engine import Chamber, ChamberError
from analysis_chamber.daemon.state_file import LOOPBACK_HOST
from analysis_chamber.guard import LeakError

logger = logging.getLogger(__name__)

# Time a client gets to send its whole request; the reply may take much longer (agent turns).
REQUEST_READ_TIMEOUT_S = 30.0


@dataclass
class ApiServer:
    """The listening server plus its in-flight connection handlers.

    Attributes:
        server: The asyncio server.
        handlers: Handler tasks still running (an agent turn can keep one alive for long).
    """

    server: asyncio.Server
    handlers: set[asyncio.Task[None]] = field(default_factory=set)

    @property
    def port(self) -> int:
        """The loopback port it listens on."""
        return self.server.sockets[0].getsockname()[1]

    async def close(self) -> None:
        """Stop listening and cancel in-flight handlers (Python 3.12 has no close_clients)."""
        self.server.close()
        handlers = list(self.handlers)
        for task in handlers:
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)
        await self.server.wait_closed()


async def start_server(chamber: Chamber, token: str) -> ApiServer:
    """Listen on a random free loopback port.

    Args:
        chamber: Carries out the routes.
        token: The bearer token every request must carry.

    Returns:
        The running ApiServer.
    """
    expected = token.encode("ascii")
    handlers: set[asyncio.Task[None]] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        handlers.add(task)
        try:
            await _serve_one(chamber, expected, reader, writer)
        finally:
            handlers.discard(task)
            writer.close()

    server = await asyncio.start_server(handle, LOOPBACK_HOST, 0, limit=MAX_LINE_BYTES)
    return ApiServer(server, handlers)


async def _serve_one(
    chamber: Chamber, token: bytes, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        request = await asyncio.wait_for(read_request(reader, token), REQUEST_READ_TIMEOUT_S)
    except (BadRequest, TimeoutError, asyncio.IncompleteReadError, ConnectionError) as error:
        logger.warning("dropped a bad request: %s", error)
        return
    status, reply = await _reply(chamber, request.path, request.body)
    payload = json.dumps(reply).encode("utf-8")
    head = (
        f"HTTP/1.1 {status.value} {status.phrase}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Connection: close\r\n\r\n"
    )
    try:
        writer.write(head.encode("ascii") + payload)
        await writer.drain()
    except ConnectionError:
        logger.warning("client left before the %s reply", request.path)


async def _reply(chamber: Chamber, path: str, body: dict[str, Any]) -> tuple[HTTPStatus, dict]:
    try:
        return HTTPStatus.OK, await dispatch(chamber, path, body)
    except (ChamberError, LeakError) as error:
        return HTTPStatus.BAD_REQUEST, {"error": str(error)}
    except Exception as error:
        logger.exception("%s failed", path)
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"internal error: {error}"}
