"""The SDK-neutral events a managed session reacts to, produced by translate.py.

Keeping these apart from claude_agent_sdk's message classes lets the daemon's
session logic be tested with plain events and keeps SDK details in one package.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantText:
    """One non-blank text block Claude wrote in the main conversation (not a subagent's)."""

    text: str


@dataclass(frozen=True)
class SessionIdentified:
    """The CLI reported which Claude session id this conversation is stored under."""

    claude_session_id: str


@dataclass(frozen=True)
class TurnEnded:
    """A turn finished, successfully or not.

    Attributes:
        claude_session_id: The session id the result was reported under.
        final_text: Claude's final reply for the turn ("" when there was none).
        is_error: The turn failed (API error, max turns, interrupted, ...).
        error_detail: Why it failed, when is_error.
        session_total_cost_usd: The CLI's running cost total for this process,
            or None when it didn't report one.
    """

    claude_session_id: str
    final_text: str
    is_error: bool
    error_detail: str | None
    session_total_cost_usd: float | None


SessionEvent = AssistantText | SessionIdentified | TurnEnded
