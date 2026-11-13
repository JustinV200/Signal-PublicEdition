"""make_can_use_tool: wraps a yes/no decider as the SDK's can_use_tool callback.

The CLI calls can_use_tool only for tool calls its permission rules would
prompt for (allow rules and acceptEdits skip it). The decider receives a
ToolCall with the CLI's own prompt sentence; this module turns its answer
into the SDK's result types.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import (
    CanUseTool,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)

# Shown to Claude as the tool result when the owner says no or the dialog times out.
DENIED_MESSAGE = (
    "The owner declined this tool call (or didn't answer in time). Don't retry it; "
    "carry on without it or explain what you need it for."
)


@dataclass(frozen=True)
class ToolCall:
    """One tool call the CLI wants approved.

    Attributes:
        tool_name: The tool, e.g. "Bash".
        tool_input: Its input as Claude sent it.
        title: The CLI's full prompt sentence, e.g. "Claude wants to read foo.txt", if sent.
    """

    tool_name: str
    tool_input: Mapping[str, Any]
    title: str | None


ToolCallDecider = Callable[[ToolCall], Awaitable[bool]]
"""Returns True to allow the call."""


def make_can_use_tool(decide: ToolCallDecider) -> CanUseTool:
    """Build the can_use_tool callback for one session.

    Args:
        decide: Decides each call; it owns any timeout.

    Returns:
        A callback returning PermissionResultAllow (input unchanged) or
        PermissionResultDeny (without interrupting the turn). A decider that
        raises denies the call.
    """

    async def can_use_tool(
        tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResult:
        call = ToolCall(tool_name, tool_input, context.title)
        try:
            is_allowed = await decide(call)
        except Exception:
            # Fail closed: Claude is told no and the turn carries on.
            logger.exception("Deciding %s failed; denying it", tool_name)
            is_allowed = False
        if is_allowed:
            return PermissionResultAllow()
        return PermissionResultDeny(message=DENIED_MESSAGE)

    return can_use_tool
