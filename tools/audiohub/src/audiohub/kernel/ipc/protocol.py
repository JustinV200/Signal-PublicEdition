"""Wire format shared by the kernel's TCP server and its client.

One request per line, UTF-8 JSON:
{"token": str, "source": str, "text": str, "priority": str}
("priority" is optional, default "normal"; "token" is the running hub's
secret, see auth_token.py; an optional "ring_through": true, allowed only on
an "urgent" note, has it spoken even while the user is asleep or away), or
{"token": str, "command": "shutdown"} to ask the hub to exit cleanly. One reply per line:
{"ok": true, "id": "<message id>"}, {"ok": true} for a shutdown,
{"ok": false, "error": "<why>"}, or for a note dropped while the user is
asleep or away {"ok": false, "error": "dropped: <why>", "dropped": true}.
Both sides validate with the same rules so a bad request fails on the client
before it is even sent.
"""

import json
from dataclasses import dataclass, replace
from typing import Any

from ..messages import PRIORITIES, Priority
from .auth_token import tokens_match

ENCODING = "utf-8"
LINE_END = b"\n"
# A line is one notification. 16 KiB is far more than anyone wants spoken at
# once, and caps what a misbehaving client can make the hub buffer.
MAX_LINE_BYTES = 16 * 1024
MAX_SOURCE_CHARS = 64
DEFAULT_PRIORITY: Priority = "normal"
REQUIRED_KEYS = frozenset({"token", "source", "text"})
ALLOWED_KEYS = REQUIRED_KEYS | {"priority", "ring_through"}
# Only notes the kernel already treats as most urgent may ring through quiet
# hours. Anything else asking to is refused, not downgraded, so a caller's bug
# shows up at once instead of as a note that silently never reaches the owner.
RING_THROUGH_PRIORITY: Priority = "urgent"
SHUTDOWN_KEYS = frozenset({"token", "command"})
SHUTDOWN_COMMAND = "shutdown"


class ProtocolError(ValueError):
    """A request or reply line that breaks the wire format."""


@dataclass(frozen=True)
class NotificationRequest:
    """A validated notification: who sent it, what to say, how important it is.

    `ring_through` notes are spoken even while the owner is asleep or away; only
    `RING_THROUGH_PRIORITY` notes may set it (checked by `parse_request`).
    """

    source: str
    text: str
    priority: Priority = DEFAULT_PRIORITY
    ring_through: bool = False


@dataclass(frozen=True)
class ShutdownRequest:
    """A request for the hub to shut down cleanly (restoring music, closing audio)."""


def validate_request(source: Any, text: Any, priority: Any) -> NotificationRequest:
    """Check notification fields and return them as a request.

    Raises:
        ProtocolError: If a field has the wrong type, is blank or too long, or
            the priority is unknown.
    """
    if not isinstance(source, str) or not source.strip():
        raise ProtocolError('"source" must be a non-blank string')
    if len(source) > MAX_SOURCE_CHARS:
        raise ProtocolError(f'"source" must be at most {MAX_SOURCE_CHARS} characters')
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError('"text" must be a non-blank string')
    if priority not in PRIORITIES:
        raise ProtocolError(f'"priority" must be one of {", ".join(PRIORITIES)}')
    return NotificationRequest(source=source.strip(), text=text, priority=priority)


def encode_request(request: NotificationRequest, token: str) -> bytes:
    """Serialize a request, with the hub's token, as one line.

    Raises:
        ProtocolError: If the encoded line is longer than `MAX_LINE_BYTES`.
    """
    payload: dict[str, Any] = {
        "token": token,
        "source": request.source,
        "text": request.text,
        "priority": request.priority,
    }
    if request.ring_through:  # omitted when false, as signal_hub_notify does
        payload["ring_through"] = True
    return _encode_line(payload)


def parse_request(line: bytes, expected_token: str) -> NotificationRequest | ShutdownRequest:
    """Parse, authenticate and validate one request line received by the server.

    Raises:
        ProtocolError: If the line is too long, not UTF-8 JSON, not an object,
            lacks the right token, has unknown or missing keys, names an
            unknown command, fails `validate_request`, or asks to ring
            through without being urgent.
    """
    data = _decode_line(line)
    # Authenticate before anything else, so a caller without the token learns
    # nothing about the request format.
    if not tokens_match(data.get("token"), expected_token):
        raise ProtocolError("missing or invalid token")
    keys = set(data)
    if "command" in keys:
        if keys != SHUTDOWN_KEYS or data["command"] != SHUTDOWN_COMMAND:
            raise ProtocolError('a command request must be {"token", "command": "shutdown"}')
        return ShutdownRequest()
    if not keys >= REQUIRED_KEYS or not keys <= ALLOWED_KEYS:
        raise ProtocolError(
            "request keys must be token, source, text and optionally priority and"
            f" ring_through; got {sorted(keys)}"
        )
    request = validate_request(data["source"], data["text"], data.get("priority", DEFAULT_PRIORITY))
    return _with_ring_through(request, data.get("ring_through", False))


def _with_ring_through(request: NotificationRequest, ring_through: Any) -> NotificationRequest:
    """`request` with its ring-through flag, refusing it on a note that isn't urgent.

    Raises:
        ProtocolError: If `ring_through` isn't a boolean, or is true on a
            note whose priority isn't `RING_THROUGH_PRIORITY`.
    """
    if not isinstance(ring_through, bool):
        raise ProtocolError('"ring_through" must be true or false')
    if ring_through and request.priority != RING_THROUGH_PRIORITY:
        raise ProtocolError(f'"ring_through" needs priority "{RING_THROUGH_PRIORITY}"')
    return replace(request, ring_through=ring_through)


def encode_ok_reply(message_id: str) -> bytes:
    """The reply line for an accepted notification."""
    return _encode_line({"ok": True, "id": message_id})


def encode_shutdown_reply() -> bytes:
    """The reply line for an accepted shutdown request."""
    return _encode_line({"ok": True})


def encode_error_reply(error: str) -> bytes:
    """The reply line for a rejected request."""
    return _encode_line({"ok": False, "error": error})


def encode_dropped_reply(reason: str) -> bytes:
    """The reply line for a note dropped unspoken, e.g. reason "the owner is asleep"."""
    # "ok" is false so clients that only know {"ok", "id"} (signal_hub_notify)
    # report it as not delivered instead of choking on a missing id.
    return _encode_line({"ok": False, "error": f"dropped: {reason}", "dropped": True})


def decode_reply(line: bytes) -> dict[str, Any]:
    """Parse one reply line received by the client.

    Raises:
        ProtocolError: If the line is not a JSON object with a boolean "ok".
    """
    data = _decode_line(line)
    if not isinstance(data.get("ok"), bool):
        raise ProtocolError('reply must have a boolean "ok"')
    return data


def _encode_line(payload: dict[str, Any]) -> bytes:
    """JSON-encode `payload` as one newline-terminated line within the size cap."""
    line = json.dumps(payload, ensure_ascii=False).encode(ENCODING) + LINE_END
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError(f"message is {len(line)} bytes; the limit is {MAX_LINE_BYTES}")
    return line


def _decode_line(line: bytes) -> dict[str, Any]:
    """Decode one line into a JSON object, enforcing the size cap."""
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError(f"line is longer than {MAX_LINE_BYTES} bytes")
    try:
        data = json.loads(line.decode(ENCODING))
    except (ValueError, RecursionError) as error:
        # ValueError covers bad UTF-8 and bad JSON; RecursionError is what
        # json raises on absurdly deep nesting such as "[[[[...".
        raise ProtocolError(f"line is not UTF-8 JSON: {error}") from error
    if not isinstance(data, dict):
        raise ProtocolError("line must be a JSON object")
    return data
