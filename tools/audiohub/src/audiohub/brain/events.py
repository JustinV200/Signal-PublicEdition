"""Events that ClaudeBrain.ask() yields while Claude answers one user turn.

The voice loop turns each ReplyText into a kernel message and uses TurnDone to
know the turn is over. InjectedTurnDone and TurnActivity only travel between a
BrainSession and ClaudeBrain. These types are SDK-neutral, so nothing
downstream of the brain needs to import claude-agent-sdk.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReplyText:
    """One assistant text block, in the order Claude wrote it.

    Attributes:
        text: The block's text, exactly as Claude wrote it (not yet cleaned for speech).
    """

    text: str


@dataclass(frozen=True)
class TurnDone:
    """The end of one turn. Always the last event of an ask() call.

    Attributes:
        duration_s: How long the turn took, in seconds.
        cost_usd: What the turn cost in US dollars, or None when the CLI didn't report it.
        is_error: True when the turn ended in an error (including an interrupt).
    """

    duration_s: float
    cost_usd: float | None
    is_error: bool


@dataclass(frozen=True)
class InjectedTurnDone:
    """The end of a turn the session started on its own, not in answer to ask().

    The CLI runs such turns when, for example, a background agent finishes. A
    BrainSession yields this instead of TurnDone so the brain doesn't end the
    user's ask() on it. ask() never yields it.
    """


@dataclass(frozen=True)
class TurnActivity:
    """The CLI is working on a turn but wrote nothing to speak: a tool call or result, thinking.

    It tells the brain a turn is running even before any text arrives, so a
    turn the CLI injected isn't mistaken for idle, and it keeps the stalled-turn
    watchdog from firing while Claude is busy. ask() never yields it.

    Attributes:
        is_subagent: True for a subagent's messages. Those also arrive from
            background agents while no turn runs, so on their own they never
            mean an injected turn has started.
        source: What the session saw, e.g. "UserMessage" (a prompt or tool
            result), for logs only, so it takes no part in equality.
    """

    is_subagent: bool = False
    source: str = field(default="", compare=False)


BrainEvent = ReplyText | TurnDone
"""Anything ask() can yield."""

SessionEvent = ReplyText | TurnDone | InjectedTurnDone | TurnActivity
"""Anything a BrainSession's event stream can yield."""
