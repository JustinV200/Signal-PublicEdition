"""DaemonServer: the loopback-only TCP server that answers IPC requests for the SessionManager.

One JSON request line in, one JSON reply line out, any number per
connection. Every request must carry the daemon's token, which the server
writes to its token file only after it has bound the port. A second daemon
that loses the race for the port therefore never replaces the live daemon's
token. A line that is
malformed or unauthenticated (an HTTP request from a web page, say) gets one
error reply and the connection is closed, so nothing after it is read. Lines
are capped at ipc.MAX_LINE_BYTES and idle connections are dropped. Refused
operations become error replies; anything unexpected is logged with its
traceback and reported as an internal error, so one bad request never takes
the daemon down.
"""

import asyncio
import ipaddress
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from claude_sessions.approvals import PermissionModeError
from claude_sessions.daemon.dispatch import dispatch
from claude_sessions.daemon.manager import SessionManager
from claude_sessions.daemon.session import SessionError
from claude_sessions.ipc import (
    LINE_END,
    MAX_LINE_BYTES,
    ProtocolError,
    encode_error,
    encode_ok,
    parse_request,
)
from claude_sessions.tokens import create_token_file

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_S = 60.0
# Refusals whose message is meant for an authenticated caller; the connection stays open.
_REFUSALS = (SessionError, PermissionModeError)


@dataclass(frozen=True)
class ListenSpec:
    """Where the daemon listens and where it publishes its token.

    Attributes:
        host: A loopback IPv4 address; anything else is refused.
        port: TCP port; 0 picks a free one (see DaemonServer.port).
        token_file: Gets a fresh token once the port is bound (config.daemon_token_file).
    """

    host: str
    port: int
    token_file: Path


class DaemonServer:
    """Serves the daemon protocol on a loopback address."""

    def __init__(
        self, manager: SessionManager, listen: ListenSpec, on_shutdown: Callable[[], None]
    ) -> None:
        """Configure the server; start() (or `async with`) begins listening.

        Args:
            manager: Runs the operations.
            listen: The address to bind and the token file to write after binding.
            on_shutdown: Called when a client sends the shutdown op.

        Raises:
            ValueError: The host isn't a loopback IPv4 address.
        """
        _require_loopback(listen.host)
        self._manager = manager
        self._listen = listen
        self._on_shutdown = on_shutdown
        self._token = ""
        self._server: asyncio.Server | None = None

    @property
    def port(self) -> int:
        """The port actually listened on.

        Raises:
            RuntimeError: The server isn't started.
        """
        if self._server is None:
            raise RuntimeError("DaemonServer isn't started")
        return self._server.sockets[0].getsockname()[1]

    async def bind(self) -> None:
        """Take the port without publishing a token or accepting connections yet.

        serve() binds first and loads the sessions file only once it holds the
        port, so a daemon that loses the race never rewrites the live one's file.

        Raises:
            OSError: The port is in use (another daemon is probably running).
        """
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._serve_connection,
            self._listen.host,
            self._listen.port,
            limit=MAX_LINE_BYTES,
            start_serving=False,
        )

    async def start(self) -> None:
        """Bind (unless bind() already did), publish a fresh token, then accept connections.

        Raises:
            OSError: The port is in use (another daemon is probably running; its
                token file is left alone), or the token file can't be written.
        """
        await self.bind()
        try:
            self._token = create_token_file(self._listen.token_file)
        except OSError:
            await self.close()
            raise
        await self._server.start_serving()
        logger.info("Sessions daemon listening on %s:%d", self._listen.host, self.port)

    async def close(self) -> None:
        """Stop listening. Safe to call twice."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def __aenter__(self) -> Self:
        """Start the server for an `async with` block."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the server when the block ends."""
        await self.close()

    async def _serve_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Answer request lines until EOF, a bad line, an oversized line or idle timeout."""
        try:
            while line := await asyncio.wait_for(_read_line(reader), IDLE_TIMEOUT_S):
                reply, keep_open = await self._reply_to(line)
                writer.write(reply)
                await writer.drain()
                if not keep_open:
                    break
        except asyncio.LimitOverrunError:
            writer.write(encode_error(f"request is longer than {MAX_LINE_BYTES} bytes"))
        except TimeoutError:
            logger.debug("Closing idle IPC connection")
        except ConnectionError as error:
            logger.debug("IPC client went away: %s", error)
        finally:
            writer.close()

    async def _reply_to(self, line: bytes) -> tuple[bytes, bool]:
        """Run one request line; return its reply and whether to keep the connection open."""
        try:
            request = parse_request(line, self._token)
        except ProtocolError as error:
            # Malformed or unauthenticated: answer once and hang up.
            logger.warning("Rejected IPC line and closed the connection: %s", error)
            return encode_error(str(error)), False
        except PermissionModeError as error:
            # Authenticated, well-formed, but asks for a refused mode such as bypassPermissions.
            logger.info("Refused IPC request: %s", error)
            return encode_error(str(error)), True
        try:
            return encode_ok(await dispatch(self._manager, request, self._on_shutdown)), True
        except _REFUSALS as error:
            logger.info("Refused IPC request: %s", error)
            return encode_error(str(error)), True
        except Exception as error:
            logger.exception("IPC request failed unexpectedly")
            return encode_error(f"internal error in the sessions daemon: {error}"), True


async def _read_line(reader: asyncio.StreamReader) -> bytes:
    """One newline-terminated line; b"" at EOF (a final line without newline still counts)."""
    try:
        return await reader.readuntil(LINE_END)
    except asyncio.IncompleteReadError as eof:
        return eof.partial


def _require_loopback(host: str) -> None:
    """Refuse any bind address other than IPv4 loopback (127.0.0.0/8)."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise ValueError(f"the daemon binds a loopback IPv4 address only, got {host!r}") from error
    if address.version != 4 or not address.is_loopback:
        raise ValueError(f"the daemon binds a loopback IPv4 address only, got {host!r}")
