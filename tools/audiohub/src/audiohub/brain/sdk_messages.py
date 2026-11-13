"""Translates claude-agent-sdk messages into the brain's session events.

Part of the thin SDK adapter. Pure logic with no I/O, so it is tested against
real SDK message dataclasses. Only top-level assistant text is spoken. Other
assistant and user messages (tool use, tool results, thinking, subagent
traffic) become TurnActivity, which shows a turn is running. System and stream
messages are skipped.
"""

from claude_agent_sdk import (
    AssistantMessage,
    ConversationResetMessage,
    Message,
    ResultMessage,
    TextBlock,
    UserMessage,
)

from audiohub.brain.events import (
    InjectedTurnDone,
    ReplyText,
    SessionEvent,
    TurnActivity,
    TurnDone,
)

MS_PER_SECOND = 1000.0

# A result's origin says which user message started the turn. Prompts sent through
# ClaudeSDKClient.query() carry no origin; "human" is the only kind an SDK host may
# stamp. Anything else (e.g. "task-notification") is a turn the CLI injected itself.
OWN_TURN_ORIGIN_KIND = "human"

# terminal_reason values that mean the turn was cut short by interrupt().
INTERRUPTED_TERMINAL_REASONS = frozenset({"aborted_streaming", "aborted_tools"})


class MessageTranslator:
    """Turns SDK messages into session events, one session at a time.

    Stateful because the CLI reports `total_cost_usd` as a running total for the
    whole session (checked against CLI 2.1.301), while TurnDone carries the cost
    of one turn. A ConversationResetMessage (e.g. after /clear) zeroes that total.
    """

    def __init__(self) -> None:
        """Start with no cost seen yet."""
        self._session_cost_usd = 0.0

    def translate(self, message: Message) -> list[SessionEvent]:
        """Translate one SDK message.

        Args:
            message: Any message from ClaudeSDKClient.receive_messages().

        Returns:
            One ReplyText per non-blank top-level text block, a single TurnDone
            (our turn) or InjectedTurnDone (a CLI-injected turn) for a
            ResultMessage, one TurnActivity for any other assistant or user
            message, or [] for anything else.
        """
        if isinstance(message, AssistantMessage):
            return _reply_texts(message) or [_activity(message)]
        if isinstance(message, UserMessage):
            # Tool results and replayed prompts, including an injected turn's prompt.
            return [_activity(message)]
        if isinstance(message, ResultMessage):
            return [self._turn_end(message)]
        if isinstance(message, ConversationResetMessage):
            self._session_cost_usd = 0.0
        return []

    def _turn_end(self, result: ResultMessage) -> TurnDone | InjectedTurnDone:
        """Build the end-of-turn event, converting the running cost into this turn's cost."""
        # Injected turns add to the running total too, so take their share either way.
        turn_cost_usd = self._take_turn_cost(result.total_cost_usd)
        if not _is_own_turn(result):
            return InjectedTurnDone()
        return TurnDone(
            duration_s=result.duration_ms / MS_PER_SECOND,
            cost_usd=turn_cost_usd,
            is_error=result.is_error or result.terminal_reason in INTERRUPTED_TERMINAL_REASONS,
        )

    def _take_turn_cost(self, session_total_usd: float | None) -> float | None:
        """Return the cost added since the last result, and remember the new total."""
        if session_total_usd is None:
            return None
        # A total that went down means the session was reset without us seeing the
        # reset message; the whole total then belongs to this turn.
        previous_total = self._session_cost_usd
        if session_total_usd < previous_total:
            previous_total = 0.0
        self._session_cost_usd = session_total_usd
        return session_total_usd - previous_total


def _is_own_turn(result: ResultMessage) -> bool:
    """Say whether a result ends a turn we started with query().

    An origin without a kind counts as ours: wrongly calling our own result
    injected would leave ask() waiting forever.
    """
    origin_kind = result.origin.get("kind") if isinstance(result.origin, dict) else None
    return origin_kind is None or origin_kind == OWN_TURN_ORIGIN_KIND


def _reply_texts(message: AssistantMessage) -> list[SessionEvent]:
    """Pick the speakable text blocks out of one assistant message."""
    # A parent_tool_use_id means a subagent wrote this. Its working notes are
    # not meant for the user; the main agent reports the outcome itself.
    if message.parent_tool_use_id is not None:
        return []
    return [
        ReplyText(block.text)
        for block in message.content
        if isinstance(block, TextBlock) and block.text.strip()
    ]


def _activity(message: AssistantMessage | UserMessage) -> TurnActivity:
    """A TurnActivity naming the message type (for logs), marked as a subagent's if it is one."""
    return TurnActivity(
        is_subagent=message.parent_tool_use_id is not None, source=type(message).__name__
    )
