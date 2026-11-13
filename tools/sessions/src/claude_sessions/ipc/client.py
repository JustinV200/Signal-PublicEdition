"""call_daemon: an asyncio client for one request to the sessions daemon.

Used by the CLI and the MCP server. Opens one connection per call: calls are
rare and short, and a fresh connection can't be left in a bad state.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from claude_sessions.ipc.protocol import (
    LINE_END,
    MAX_LINE_BYTES,
    ProtocolError,
    decode_line,
    encode_request,
)

CONNECT_TIMEOUT_S = 3.0
# Every op answers quickly (start connects in the background), so a slow
# reply means the daemon is stuck.
REPLY_TIMEOUT_S = 30.0


class DaemonNotRunningError(ConnectionError):
    """Nothing is listening at the daemon's address."""


class DaemonRequestError(RuntimeError):
    """The daemon answered and refused the request; the message says why."""


@dataclass(frozen=True)
class DaemonEndpoint:
    """Where the daemon listens and the token its requests must carry.

    Attributes:
        host: The daemon's loopback address.
        port: The daemon's port (0 lets a server pick one).
        token: The secret from the daemon's token file.
    """

    host: str
    port: int
    token: str


async def call_daemon(endpoint: DaemonEndpoint, op: str, args: dict[str, Any] | None = None) -> Any:
    """Send one request and return the daemon's result.

    Args:
        endpoint: The daemon's address and token.
        op: The operation, e.g. "status".
        args: Its arguments (validated before sending).

    Returns:
        The decoded "result" of an ok reply.

    Raises:
        ProtocolError: The request is invalid, or the reply is malformed.
        PermissionModeError: A refused permission_mode was requested.
        DaemonNotRunningError: The daemon can't be reached.
        DaemonRequestError: The daemon refused the request.
        TimeoutError: The daemon didn't reply in time.
    """
    line = encode_request(op, args, endpoint.token)
    host, port = endpoint.host, endpoint.port
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, limit=MAX_LINE_BYTES + 1), CONNECT_TIMEOUT_S
        )
    except (ConnectionRefusedError, TimeoutError) as error:
        raise DaemonNotRunningError(
            f"the sessions daemon isn't running on {host}:{port}"
        ) from error
    try:
        writer.write(line)
        await writer.drain()
        reply = await asyncio.wait_for(reader.readuntil(LINE_END), REPLY_TIMEOUT_S)
    except asyncio.IncompleteReadError as error:
        raise ProtocolError("the daemon closed the connection without a reply") from error
    except asyncio.LimitOverrunError as error:
        raise ProtocolError(f"the daemon's reply is longer than {MAX_LINE_BYTES} bytes") from error
    finally:
        writer.close()
    return _result_of(decode_line(reply))


def _result_of(reply: dict[str, Any]) -> Any:
    """The result of an ok reply; raise DaemonRequestError for an error reply."""
    if reply.get("ok") is True:
        return reply.get("result")
    if reply.get("ok") is False:
        raise DaemonRequestError(str(reply.get("error") or "the daemon refused the request"))
    raise ProtocolError('the reply has no boolean "ok"')
