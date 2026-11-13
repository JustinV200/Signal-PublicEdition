"""Fan-out of JSON messages to every connected board page over WebSocket."""

import json
import logging
from typing import Any

from aiohttp import WSCloseCode, web

log = logging.getLogger(__name__)


class BroadcastHub:
    """The set of open board-page WebSockets, and a way to send all of them a message."""

    def __init__(self) -> None:
        self._sockets: set[web.WebSocketResponse] = set()

    @property
    def page_count(self) -> int:
        """How many board pages are connected right now."""
        return len(self._sockets)

    def add(self, socket: web.WebSocketResponse) -> None:
        """Start sending broadcasts to an open WebSocket."""
        self._sockets.add(socket)

    def discard(self, socket: web.WebSocketResponse) -> None:
        """Stop sending broadcasts to a WebSocket (no error if it was never added)."""
        self._sockets.discard(socket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send one JSON message to every page. A page whose socket fails is dropped.

        Args:
            message: A JSON-serializable dict with a "type" key.
        """
        text = json.dumps(message)
        for socket in list(self._sockets):
            try:
                await socket.send_str(text)
            except ConnectionError as error:
                # The page went away mid-send; its handler will also notice and clean up.
                log.info("dropping board page whose socket failed: %s", error)
                self.discard(socket)

    async def close_all(self) -> None:
        """Close every page's socket (on daemon shutdown); pages reconnect when it's back."""
        for socket in list(self._sockets):
            await socket.close(code=WSCloseCode.GOING_AWAY, message=b"daemon shutting down")
        self._sockets.clear()
