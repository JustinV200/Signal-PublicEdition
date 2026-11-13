"""`send_notification`: a blocking stdlib client for a running hub's `KernelServer`.

Used by the MCP `notify` tool and `audiohub notify`, which run in other
processes and just need to hand a message to the hub and get its id back.
"""

import socket
from pathlib import Path

from ..messages import Priority
from .auth_token import DEFAULT_TOKEN_PATH, read_token
from .protocol import (
    MAX_LINE_BYTES,
    ProtocolError,
    decode_reply,
    encode_request,
    validate_request,
)

CONNECT_TIMEOUT_S = 3.0
REPLY_TIMEOUT_S = 5.0
START_HINT = "start it with `uv run audiohub run` in tools/audiohub"


class HubNotRunningError(ConnectionError):
    """Nothing is listening at the hub's address: the hub isn't running."""


class NotificationRejectedError(RuntimeError):
    """The hub answered but refused the notification; the message says why."""


class NotificationDroppedError(NotificationRejectedError):
    """The hub dropped the note unspoken because the owner is asleep or away.

    The message is the hub's own, e.g. "dropped: the owner is asleep".
    """


def send_notification(
    host: str,
    port: int,
    source: str,
    text: str,
    priority: Priority = "normal",
    *,
    token_path: Path = DEFAULT_TOKEN_PATH,
) -> str:
    """Send one notification to the hub and return the id it was given.

    Over the usual parameter limit because the first five are the contract
    the audiohub brief fixes for every caller; `token_path` is keyword-only
    and only tests change it.

    Args:
        host: Hub address, normally `IpcSettings.host` (127.0.0.1).
        port: Hub port, normally `IpcSettings.port`.
        source: Who is speaking, e.g. "build-agent".
        text: What the user should hear.
        priority: "urgent", "high", "normal" or "low".
        token_path: The running hub's token file.

    Returns:
        The kernel's id for the queued message, e.g. "m12".

    Raises:
        ProtocolError: If the fields are invalid or too long, or the hub's
            reply is malformed.
        HubNotRunningError: If the hub can't be reached or wrote no token.
        NotificationDroppedError: If the hub dropped it (the owner is asleep or away).
        NotificationRejectedError: If the hub refused the request.
        TimeoutError: If the hub accepted the connection but never replied.
    """
    request = validate_request(source, text, priority)
    try:
        token = read_token(token_path)
    except FileNotFoundError as error:
        raise HubNotRunningError(
            f"audiohub isn't running (no IPC token at {token_path}); {START_HINT}"
        ) from error
    line = encode_request(request, token)
    try:
        connection = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S)
    except (ConnectionRefusedError, TimeoutError) as error:
        raise HubNotRunningError(
            f"audiohub isn't running on {host}:{port} ({error}); {START_HINT}"
        ) from error
    with connection:
        connection.settimeout(REPLY_TIMEOUT_S)
        connection.sendall(line)
        reply = _read_reply_line(connection)
    return _message_id_from(reply)


def _read_reply_line(connection: socket.socket) -> bytes:
    """Read the hub's single reply line."""
    with connection.makefile("rb") as stream:
        line = stream.readline(MAX_LINE_BYTES + 1)
    if not line.endswith(b"\n"):
        raise ProtocolError("the hub closed the connection without a complete reply")
    return line


def _message_id_from(reply: bytes) -> str:
    """Return the id from an ok reply, or raise for an error reply."""
    data = decode_reply(reply)
    if not data["ok"] and data.get("dropped") is True:
        raise NotificationDroppedError(str(data.get("error")))
    if not data["ok"]:
        raise NotificationRejectedError(f"the hub rejected the notification: {data.get('error')}")
    message_id = data.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise ProtocolError('an ok reply must carry a string "id"')
    return message_id
