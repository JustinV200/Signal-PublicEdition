"""send_to_hub: a tiny asyncio client for the audiohub voice hub's kernel server.

Wire format (owned by tools/audiohub, see its kernel/ipc/README.md; not
imported, to keep the tools independent): one UTF-8 JSON request line
{"source", "text", "priority", "token"} (plus "ring_through": true when
set), then one reply line
{"ok": true, "id": "..."} or {"ok": false, "error": "..."}. A note dropped
unspoken because the owner is asleep or away gets
{"ok": false, "error": "dropped: <reason>", "dropped": true}. The token is the
one audiohub publishes in its token file (see Notifier).
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Literal

Priority = Literal["urgent", "high", "normal", "low"]

ENCODING = "utf-8"
# The hub refuses lines over 16 KiB and sources over 64 characters.
MAX_LINE_BYTES = 16 * 1024
MAX_SOURCE_CHARS = 64
CONNECT_TIMEOUT_S = 3.0
REPLY_TIMEOUT_S = 5.0
# The only drop reasons passed on; any other dropped reply counts as a refusal,
# so a reason shown to a caller is always one of these fixed strings.
DROP_REASONS = frozenset({"the owner is asleep", "the owner is away"})
DROPPED_PREFIX = "dropped: "


class HubUnavailableError(ConnectionError):
    """Nothing is listening at the hub's address: the voice hub isn't running."""


class HubRejectedError(RuntimeError):
    """The hub answered, but refused the message or sent a reply we can't read."""


class HubDroppedError(HubRejectedError):
    """The hub dropped the note unspoken because the owner is asleep or away.

    Attributes:
        reason: One of DROP_REASONS, e.g. "the owner is asleep".
    """

    def __init__(self, reason: str) -> None:
        """Args: reason: One of DROP_REASONS."""
        super().__init__(f"the hub dropped the note: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class HubNote:
    """One message for the owner's ears.

    Attributes:
        source: Who is speaking, at most 64 characters, e.g. "session:OtherRepo".
        text: What the owner should hear.
        priority: How urgent the kernel should treat it.
        ring_through: Speak it even while the owner is asleep or away. The hub
            accepts this only on an "urgent" note and refuses any other. The owner
            may still not answer, so callers must plan for that.
    """

    source: str
    text: str
    priority: Priority = "normal"
    ring_through: bool = False


async def send_to_hub(host: str, port: int, note: HubNote, token: str) -> str:
    """Deliver one note to the hub and return the id the hub gave it.

    Args:
        host: The hub's loopback address.
        port: The hub's kernel port (8765 by default).
        note: The message to deliver.
        token: The hub kernel's IPC token.

    Returns:
        The hub's message id, e.g. "m12".

    Raises:
        HubUnavailableError: The hub can't be reached.
        HubDroppedError: The hub dropped it unspoken (the owner is asleep or away).
        HubRejectedError: The hub refused the note or replied with something unreadable.
        TimeoutError: The hub accepted the connection but didn't reply in time.
    """
    line = _encode(note, token)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), CONNECT_TIMEOUT_S
        )
    except (ConnectionRefusedError, TimeoutError) as error:
        raise HubUnavailableError(f"the voice hub isn't running on {host}:{port}") from error
    try:
        writer.write(line)
        await writer.drain()
        reply = await asyncio.wait_for(reader.readline(), REPLY_TIMEOUT_S)
    finally:
        writer.close()
    return _message_id(reply)


def _encode(note: HubNote, token: str) -> bytes:
    """One request line carrying the token, with the source cut to the hub's limit."""
    payload: dict[str, object] = {
        "source": note.source[:MAX_SOURCE_CHARS],
        "text": note.text,
        "priority": note.priority,
        "token": token,
    }
    if note.ring_through:  # only sent when set, so the default line is unchanged
        payload["ring_through"] = True
    line = json.dumps(payload, ensure_ascii=False).encode(ENCODING) + b"\n"
    if len(line) > MAX_LINE_BYTES:
        raise HubRejectedError(f"note is {len(line)} bytes; the hub allows {MAX_LINE_BYTES}")
    return line


def _message_id(reply: bytes) -> str:
    """The id from an ok reply; raise HubRejectedError for anything else."""
    try:
        data = json.loads(reply.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HubRejectedError(f"unreadable reply from the hub: {reply[:200]!r}") from error
    if not isinstance(data, dict) or data.get("ok") is not True:
        _raise_if_dropped(data)
        error_text = data.get("error") if isinstance(data, dict) else data
        raise HubRejectedError(f"the hub refused the note: {error_text}")
    message_id = data.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise HubRejectedError('the hub\'s ok reply had no "id"')
    return message_id


def _raise_if_dropped(data: object) -> None:
    """Raise HubDroppedError for a dropped reply whose reason is in DROP_REASONS."""
    if not isinstance(data, dict) or data.get("dropped") is not True:
        return
    error_text = data.get("error")
    if isinstance(error_text, str) and error_text.startswith(DROPPED_PREFIX):
        reason = error_text.removeprefix(DROPPED_PREFIX)
        if reason in DROP_REASONS:
            raise HubDroppedError(reason)
