"""`KernelServer`: a loopback-only TCP server that feeds notifications into the kernel.

Other processes (the MCP server, the `audiohub notify` command, scripts) send
newline-delimited JSON requests; each valid one becomes an `OutboundMessage`
submitted to the `Kernel`, and the reply carries its id. While the owner is
asleep or away (presence.py) a notification is dropped instead, and the reply
says why, unless it is an urgent note marked ring_through (protocol.py).
A shutdown request sets `wait_for_shutdown`, which the conversation loop
awaits to exit cleanly (the console's Voice Stop sends it).

Every request must carry the token the server writes on start (auth_token.py),
and the first invalid line (bad JSON, bad token, too long) gets an error reply
and ends the connection. Together these stop a web page from making the hub
speak: a browser POST starts with an HTTP request line, which is invalid, and
the page can't read the token file anyway.
"""

import asyncio
import ipaddress
import logging
from pathlib import Path
from types import TracebackType

from ..facade import Kernel
from ..messages import create_message
from .auth_token import DEFAULT_TOKEN_PATH, create_token_file, remove_token_file
from .presence import PresenceFiles
from .protocol import (
    LINE_END,
    MAX_LINE_BYTES,
    ProtocolError,
    ShutdownRequest,
    encode_dropped_reply,
    encode_error_reply,
    encode_ok_reply,
    encode_shutdown_reply,
    parse_request,
)

logger = logging.getLogger(__name__)

# TODO: move these tunables to IpcSettings once audiohub.config is free to edit.
# A client that sends nothing for this long is disconnected, so an idle or
# stuck connection can't hold resources forever.
IDLE_TIMEOUT_S = 30.0
WRITE_TIMEOUT_S = 5.0  # a client that stops reading can't stall its handler
CLOSE_TIMEOUT_S = 2.0  # how long close() waits for connections to wind down
MAX_CONNECTIONS = 16  # local notifiers are few; more than this is a runaway client
TOO_MANY_CONNECTIONS = "too many connections to the hub; try again shortly"


class KernelServer:
    """Accepts notification requests on 127.0.0.1 and submits them to a `Kernel`."""

    def __init__(
        self,
        kernel: Kernel,
        host: str,
        port: int,
        token_path: Path = DEFAULT_TOKEN_PATH,
        *,
        presence: PresenceFiles | None = None,
    ) -> None:
        """Configure the server; call `start` (or use `async with`) to listen.

        Args:
            kernel: Where accepted messages go.
            host: A loopback IPv4 address (normally `IpcSettings.host`); anything
                else is refused.
            port: TCP port; 0 picks a free one (see `port`).
            token_path: Where to write the request token. Tests use a temp
                file so they never touch a real hub's token.
            presence: Where to read whether the owner is asleep or away; None
                never drops a notification (tests).

        Raises:
            ValueError: If `host` is not a loopback IPv4 address.
        """
        _require_loopback(host)
        self._kernel = kernel
        self._host = host
        self._requested_port = port
        self._token_path = token_path
        self._token = ""
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._presence = presence
        self._shutdown_requested = asyncio.Event()

    @property
    def port(self) -> int:
        """The port actually listened on (useful when 0 was requested).

        Raises:
            RuntimeError: If the server has not been started.
        """
        if self._server is None:
            raise RuntimeError("KernelServer is not started")
        return self._server.sockets[0].getsockname()[1]

    async def wait_for_shutdown(self) -> None:
        """Return once a client has asked the hub to shut down."""
        await self._shutdown_requested.wait()

    async def start(self) -> None:
        """Start listening and write a fresh token. Connections are served in the background.

        Raises:
            OSError: If the address is in use or can't be bound, or the token
                file can't be written (the listener is closed again).
        """
        # limit= caps how much one unterminated line can make us buffer.
        self._server = await asyncio.start_server(
            self._serve_connection, self._host, self._requested_port, limit=MAX_LINE_BYTES
        )
        try:
            self._token = create_token_file(self._token_path)
        except OSError:
            await self.close()
            raise
        logger.info("kernel IPC listening on %s:%d", self._host, self.port)

    async def close(self) -> None:
        """Stop accepting, close open connections, and wait (briefly) for them to end."""
        if self._server is None:
            return
        if self._token:
            remove_token_file(self._token_path, self._token)
            self._token = ""
        self._server.close()
        # Since Python 3.12 wait_closed() also waits for every open connection,
        # so close them rather than wait out their idle timeout.
        for writer in list(self._writers):
            writer.close()
        try:
            await asyncio.wait_for(self._server.wait_closed(), CLOSE_TIMEOUT_S)
        except TimeoutError:
            logger.warning("kernel IPC connections still closing after %.0f s", CLOSE_TIMEOUT_S)
        self._server = None

    async def __aenter__(self) -> "KernelServer":
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def _serve_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Answer every request line on one connection until EOF, error or timeout."""
        if len(self._writers) >= MAX_CONNECTIONS:
            logger.warning("refusing kernel IPC connection: %d already open", MAX_CONNECTIONS)
            await _send_and_close(writer, encode_error_reply(TOO_MANY_CONNECTIONS))
            return
        self._writers.add(writer)
        try:
            while line := await _read_line(reader):
                reply, is_valid = self._handle_line(line)
                await _send(writer, reply)
                if not is_valid:
                    break  # the first invalid line ends the connection
        except asyncio.LimitOverrunError:
            await _send_and_close(
                writer, encode_error_reply(f"line is longer than {MAX_LINE_BYTES} bytes")
            )
        except TimeoutError:
            logger.debug("closing idle or stalled kernel IPC connection")
        except ConnectionError as error:
            logger.debug("kernel IPC client went away: %s", error)
        finally:
            self._writers.discard(writer)
            await _close_quietly(writer)

    def _handle_line(self, line: bytes) -> tuple[bytes, bool]:
        """Authenticate and validate one request, act on it; return (reply, is_valid)."""
        try:
            request = parse_request(line, self._token)
        except ProtocolError as error:
            logger.warning("rejected kernel IPC request: %s", error)
            return encode_error_reply(str(error)), False
        if isinstance(request, ShutdownRequest):
            # The reply is written before the hub closes this server, and
            # closing a transport flushes what it has buffered.
            logger.info("shutdown requested over kernel IPC")
            self._shutdown_requested.set()
            return encode_shutdown_reply(), True
        quiet_reason = self._presence.quiet_reason() if self._presence else None
        if quiet_reason is not None and not request.ring_through:
            logger.info("dropped notification from %s: %s", request.source, quiet_reason)
            return encode_dropped_reply(quiet_reason), True
        if quiet_reason is not None:
            logger.info("notification from %s rang through: %s", request.source, quiet_reason)
        # A notification is never a direct reply, so IPC can't use the
        # dispatcher's fast path (the protocol also rejects the key).
        message = create_message(
            request.source, request.text, request.priority, is_direct_reply=False
        )
        self._kernel.submit(message)
        logger.info("notification %s from %s (%s)", message.id, message.source, message.priority)
        return encode_ok_reply(message.id), True


async def _read_line(reader: asyncio.StreamReader) -> bytes:
    """Read one newline-terminated line; b"" at EOF.

    Raises:
        asyncio.LimitOverrunError: If the line is longer than the reader's limit.
        TimeoutError: If nothing arrives within `IDLE_TIMEOUT_S`.
    """
    try:
        return await asyncio.wait_for(reader.readuntil(LINE_END), IDLE_TIMEOUT_S)
    except asyncio.IncompleteReadError as eof:
        # A final request without its newline still counts.
        return eof.partial


async def _send(writer: asyncio.StreamWriter, line: bytes) -> None:
    """Write one reply line, waiting at most `WRITE_TIMEOUT_S` for it to flush.

    Raises:
        TimeoutError: If the client stops reading.
        ConnectionError: If the client went away.
    """
    writer.write(line)
    await asyncio.wait_for(writer.drain(), WRITE_TIMEOUT_S)


async def _send_and_close(writer: asyncio.StreamWriter, line: bytes) -> None:
    """Best-effort final reply before hanging up; the peer may already be gone."""
    try:
        await _send(writer, line)
    except (TimeoutError, ConnectionError) as error:
        logger.debug("could not send final kernel IPC reply: %r", error)
    await _close_quietly(writer)


async def _close_quietly(writer: asyncio.StreamWriter) -> None:
    """Close a connection, waiting at most `WRITE_TIMEOUT_S`; the peer may already be gone."""
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), WRITE_TIMEOUT_S)
    except (TimeoutError, ConnectionError) as error:
        logger.debug("kernel IPC connection did not close cleanly: %r", error)


def _require_loopback(host: str) -> None:
    """Refuse any bind address other than IPv4 loopback (127.0.0.0/8)."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError(
            f"KernelServer binds a loopback IPv4 address only, got {host!r}"
        ) from error
    if address.version != 4 or not address.is_loopback:
        raise ValueError(f"KernelServer binds a loopback IPv4 address only, got {host!r}")
