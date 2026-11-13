"""Message and decision types shared by every part of the kernel.

An `OutboundMessage` is anything bound for the user's ears: a brain reply or a
notification from another agent. The dispatcher turns
pending messages into `Decision`s (deliver, hold or drop).
"""

import itertools
import time
from dataclasses import dataclass, field
from typing import Literal, get_args

Priority = Literal["urgent", "high", "normal", "low"]
Action = Literal["deliver", "hold", "drop"]

# Most important first; the speaking order sorts by this rank.
PRIORITIES: tuple[Priority, ...] = get_args(Priority)
ACTIONS: tuple[Action, ...] = get_args(Action)
PRIORITY_RANK: dict[str, int] = {name: rank for rank, name in enumerate(PRIORITIES)}

MESSAGE_ID_PREFIX = "m"

# A process-wide counter keeps ids short ("m1", "m2", ...) so Sonnet can quote
# them cheaply. next() on itertools.count is atomic under the GIL, so ids stay
# unique even when messages are created from several threads.
_id_counter = itertools.count(1)


def new_message_id() -> str:
    """Return a short id that is unique within this process, such as "m7"."""
    return f"{MESSAGE_ID_PREFIX}{next(_id_counter)}"


def word_count(text: str) -> int:
    """Return the number of whitespace-separated words in `text`."""
    return len(text.split())


@dataclass(frozen=True)
class OutboundMessage:
    """One message waiting to be spoken to the user.

    Attributes:
        id: Short unique id (see `new_message_id`).
        source: Who sent it, e.g. "claude" or "build-agent".
        text: What to say, verbatim.
        priority: "urgent", "high", "normal" or "low".
        created_at: Unix timestamp (seconds) when the message was created.
        is_direct_reply: True for Claude's answer to what the user just said;
            spoken first, and short ones skip Sonnet (the dispatcher's fast path).

    Raises:
        ValueError: If `priority` is unknown or `id`, `source` or `text` is blank.
    """

    id: str
    source: str
    text: str
    priority: Priority
    created_at: float
    is_direct_reply: bool = False

    def __post_init__(self) -> None:
        if self.priority not in PRIORITIES:
            raise ValueError(f"unknown priority {self.priority!r}; expected one of {PRIORITIES}")
        for name in ("id", "source", "text"):
            if not getattr(self, name).strip():
                raise ValueError(f"message {name} must not be blank")


@dataclass(frozen=True)
class Decision:
    """The dispatcher's verdict on one pending message.

    Attributes:
        message_id: Id of the message this decision is about.
        action: "deliver" (speak now), "hold" (ask again later) or "drop".
        text: Condensed replacement text for a delivery, or None to speak the
            original verbatim. Always None for hold and drop.
        reason: Short explanation; a drop names the delivered message it repeats.
    """

    message_id: str
    action: Action
    text: str | None
    reason: str


@dataclass(frozen=True)
class DeliveredRecord:
    """A message that was handed out for speaking, and the words actually used."""

    message: OutboundMessage
    spoken_text: str
    delivered_at: float = field(default_factory=time.time)


def create_message(
    source: str,
    text: str,
    priority: Priority = "normal",
    *,
    is_direct_reply: bool = False,
) -> OutboundMessage:
    """Build an `OutboundMessage` with a fresh id and the current time.

    Args:
        source: Who is sending the message.
        text: What to say.
        priority: How important it is (default "normal").
        is_direct_reply: Whether this answers what the user just said.

    Returns:
        The new message.

    Raises:
        ValueError: If any field is invalid (see `OutboundMessage`).
    """
    return OutboundMessage(
        id=new_message_id(),
        source=source,
        text=text,
        priority=priority,
        created_at=time.time(),
        is_direct_reply=is_direct_reply,
    )
