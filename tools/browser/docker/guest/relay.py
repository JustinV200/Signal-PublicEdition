"""The token-checking TCP relay in front of Edge's CDP port.

Part of the docker backend's guest (refdocs/research/docker-browser.md section 4). The relay
is the container's only TCP listener. Every connection must open with a GET
request carrying `Authorization: Bearer <token>`; anything else (no token, a
wrong one, a malformed or oversized head, or nothing within HEAD_TIMEOUT_S)
gets a 401 and is closed. An authenticated connection has its Authorization
header stripped and is then piped both ways to Edge on 127.0.0.1. The Host
header is forwarded unchanged, because Edge builds `webSocketDebuggerUrl` from
it.

Deviation from refdocs/codingrules.md section 7, on purpose: the relay binds
0.0.0.0 inside the container, because Docker's port forwarding arrives on the
container's interface. The host publishes it on 127.0.0.1 only, and the token
protects it from other containers on the bridge.
"""

import asyncio
import hmac
import logging
import time
from collections.abc import Callable
from typing import NamedTuple

logger = logging.getLogger(__name__)

RELAY_HOST = "0.0.0.0"
RELAY_PORT = 9333
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
HEAD_END = b"\r\n\r\n"
HEAD_LIMIT_BYTES = 16 * 1024
HEAD_TIMEOUT_S = 5.0
PIPE_CHUNK_BYTES = 64 * 1024
# Exit when no authenticated connection has been open for this long (also
# counted from start, so a host that never connects doesn't leave us running).
IDLE_EXIT_S = 60.0
# (host, port)
Address = tuple[str, int]
UNAUTHORIZED = b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


class ConnectionTracker:
    """Counts open authenticated connections and how long the count has been zero."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Start idle, with the idle clock running from now."""
        self._clock = clock
        self._active = 0
        self._idle_since = clock()

    def opened(self) -> None:
        """Record a newly authenticated connection."""
        self._active += 1

    def closed(self) -> None:
        """Record that an authenticated connection ended."""
        self._active -= 1
        if self._active == 0:
            self._idle_since = self._clock()

    def idle_for_s(self) -> float:
        """Seconds since the last authenticated connection closed (0 while one is open)."""
        return 0.0 if self._active else self._clock() - self._idle_since


def authorized_head(head: bytes, token: str) -> bytes | None:
    """Check one request head and return it, minus Authorization, if it carries `token`.

    Args:
        head: The bytes up to and including the blank line that ends the headers.
        token: The relay token.

    Returns:
        The head to forward to Edge, or None if the request is malformed, isn't a
        GET, or lacks exactly one Authorization header equal to "Bearer <token>".
    """
    try:
        lines = head.decode("ascii").removesuffix("\r\n\r\n").split("\r\n")
    except UnicodeDecodeError:
        return None
    request_parts = lines[0].split(" ")
    if len(request_parts) != 3:
        return None
    method, target, version = request_parts
    if method != "GET" or not target.startswith("/") or version != "HTTP/1.1":
        return None
    kept, credentials = [lines[0]], []
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if not separator or not name or name != name.strip():
            return None
        if name.lower() == "authorization":
            credentials.append(value.strip())
        else:
            kept.append(line)
    expected = f"Bearer {token}".encode("ascii")
    if len(credentials) != 1 or not hmac.compare_digest(credentials[0].encode("ascii"), expected):
        return None
    return ("\r\n".join(kept) + "\r\n\r\n").encode("ascii")


async def serve(
    token: str,
    tracker: ConnectionTracker,
    *,
    listen: Address = (RELAY_HOST, RELAY_PORT),
    upstream: Address = (CDP_HOST, CDP_PORT),
) -> asyncio.Server:
    """Start the relay. Call only once Edge's CDP answers.

    Args:
        token: The relay token every connection must carry.
        tracker: Counts the authenticated connections (for the idle exit).
        listen: Where to listen; the defaults are the container's. Host-side tests
            pass a loopback address and port 0.
        upstream: Edge's CDP address.
    """

    async def on_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _handle(reader, writer, _Peer(token, tracker, upstream))

    # `limit` caps readuntil, so an endless head fails fast instead of buffering.
    host, port = listen
    return await asyncio.start_server(on_connection, host, port, limit=HEAD_LIMIT_BYTES)


class _Peer(NamedTuple):
    """What every connection handler needs: the token, the tracker, Edge's address."""

    token: str
    tracker: ConnectionTracker
    upstream: Address


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: _Peer) -> None:
    head = await _read_head(reader)
    forwarded = authorized_head(head, peer.token) if head is not None else None
    if forwarded is None:
        logger.warning("rejected a connection: missing, malformed or unauthenticated request")
        await _close_with(writer, UNAUTHORIZED)
        return
    tracker = peer.tracker
    tracker.opened()
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(*peer.upstream)
        logger.info("accepted %s", _describe(forwarded))
        upstream_writer.write(forwarded)
        await asyncio.gather(_pipe(reader, upstream_writer), _pipe(upstream_reader, writer))
    except OSError as error:
        logger.error("couldn't reach Edge's CDP port: %s", type(error).__name__)
        writer.close()
    finally:
        tracker.closed()


async def _read_head(reader: asyncio.StreamReader) -> bytes | None:
    try:
        return await asyncio.wait_for(reader.readuntil(HEAD_END), HEAD_TIMEOUT_S)
    except (TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, OSError):
        # Too slow, too long, or the peer hung up: all treated as unauthenticated.
        return None


async def _pipe(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
    try:
        while chunk := await source.read(PIPE_CHUNK_BYTES):
            sink.write(chunk)
            await sink.drain()
    except OSError as error:
        # A reset from either side is how CDP connections usually end.
        logger.debug("relay pipe ended: %s", type(error).__name__)
    finally:
        sink.close()


async def _close_with(writer: asyncio.StreamWriter, reply: bytes) -> None:
    try:
        writer.write(reply)
        await writer.drain()
    except OSError as error:
        logger.debug("peer left before the 401: %s", type(error).__name__)
    finally:
        writer.close()


def _describe(forwarded: bytes) -> str:
    """'websocket /path' or 'GET /path', without the query, for the log."""
    request_line, _, headers = forwarded.decode("ascii").partition("\r\n")
    path = request_line.split(" ")[1].split("?")[0]
    is_upgrade = "upgrade: websocket" in headers.lower()
    return f"{'websocket' if is_upgrade else 'GET'} {path}"
