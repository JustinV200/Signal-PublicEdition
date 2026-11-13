"""The routes `ConversationState.route` gives a transcript, and the hub's `Phase`.

Plain frozen data, so the state machine, the conversation and tests can
compare them. Fields that only explain a route (for the log and the chime)
are left out of equality: `Ask("x")` is the same route however it was woken.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Phase(StrEnum):
    """What the hub is doing, as shown on the status line."""

    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass(frozen=True)
class Ask:
    """Send `request` (wake phrase stripped) to the brain.

    Attributes:
        request: What the user asked, in their own words.
        has_wake_phrase: Whether they said a wake phrase (the hub chimes),
            rather than replying in the follow-up window.
    """

    request: str
    has_wake_phrase: bool = field(default=False, compare=False)


@dataclass(frozen=True)
class Attend:
    """Only the wake phrase was said: open the follow-up window for the request."""


@dataclass(frozen=True)
class Cancel:
    """Interrupt Claude and drop whatever it hasn't said yet."""


@dataclass(frozen=True)
class Echo:
    """The mic heard Claude's own words, not the user.

    Attributes:
        compared_with: The text of Claude's that the transcript matched.
        started_after_audio_s: When the utterance began, in seconds after
            Claude's audio stopped (negative: before), or None while it played.
    """

    compared_with: str = field(default="", compare=False)
    started_after_audio_s: float | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Ignore:
    """Not addressed to Claude."""


@dataclass(frozen=True)
class BargeIn:
    """The user cut in while Claude was talking: stop its speech, then follow `then`."""

    then: Ask | Attend | Cancel


Route = Ask | Attend | Cancel | Echo | Ignore | BargeIn
