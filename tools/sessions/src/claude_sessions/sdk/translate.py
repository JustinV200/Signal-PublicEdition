"""translate_message: claude-agent-sdk messages -> the session events the daemon reacts to.

Pure logic with no I/O. Only top-level assistant text is kept: subagent
traffic, tool use, thinking and other system messages are dropped, because
status shows what Claude told its user, not its working notes.
"""

from claude_agent_sdk import AssistantMessage, Message, ResultMessage, SystemMessage, TextBlock

from claude_sessions.sdk.events import AssistantText, SessionEvent, SessionIdentified, TurnEnded

INIT_SUBTYPE = "init"
SUCCESS_SUBTYPE = "success"


def translate_message(message: Message) -> list[SessionEvent]:
    """Translate one SDK message into zero or more session events.

    Args:
        message: Any message from ClaudeSDKClient.receive_messages().

    Returns:
        AssistantText per non-blank top-level text block, SessionIdentified
        for the CLI's init message, TurnEnded for a result, else [].
    """
    if isinstance(message, AssistantMessage):
        return _assistant_texts(message)
    if isinstance(message, ResultMessage):
        return [_turn_ended(message)]
    if isinstance(message, SystemMessage) and message.subtype == INIT_SUBTYPE:
        session_id = message.data.get("session_id")
        if isinstance(session_id, str) and session_id:
            return [SessionIdentified(session_id)]
    return []


def _assistant_texts(message: AssistantMessage) -> list[SessionEvent]:
    """The main agent's text blocks; a parent_tool_use_id means a subagent wrote it."""
    if message.parent_tool_use_id is not None:
        return []
    return [
        AssistantText(block.text)
        for block in message.content
        if isinstance(block, TextBlock) and block.text.strip()
    ]


def _turn_ended(result: ResultMessage) -> TurnEnded:
    """Summarise a result, treating any non-success subtype as a failed turn."""
    is_error = result.is_error or result.subtype != SUCCESS_SUBTYPE
    return TurnEnded(
        claude_session_id=result.session_id,
        final_text=result.result or "",
        is_error=is_error,
        error_detail=_error_detail(result) if is_error else None,
        session_total_cost_usd=result.total_cost_usd,
    )


def _error_detail(result: ResultMessage) -> str:
    """The most specific failure reason the result carries."""
    if result.errors:
        return "; ".join(result.errors)
    if result.result:
        return result.result
    return result.terminal_reason or result.subtype
