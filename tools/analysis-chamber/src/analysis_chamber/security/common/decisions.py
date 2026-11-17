"""PreToolUse hook outputs: the deny and allow results every chamber security hook returns.

Output shape per claude-agent-sdk 0.2.168 `SyncHookJSONOutput` /
`PreToolUseHookSpecificOutput`. The spike showed a "deny" holds under bypassPermissions.
fail_closed wraps each hook so a crash in a check blocks the call instead of letting it by.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# The SDK's HookCallback shape: (hook_input, tool_use_id, context) -> output.
SecurityHook = Callable[[dict[str, Any], str | None, Any], Awaitable[dict[str, Any]]]


def deny(reason: str) -> dict[str, Any]:
    """Build a PreToolUse output that blocks the tool call.

    Args:
        reason: Shown to the model, so it says what to do instead.

    Returns:
        The hook output dict.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def allow() -> dict[str, Any]:
    """Return an empty output: "no opinion", so the call goes ahead under bypass mode."""
    return {}


def fail_closed(hook: SecurityHook) -> SecurityHook:
    """Wrap a hook so any exception it raises becomes a deny, never an allow.

    Args:
        hook: A PreToolUse hook (SDK HookCallback signature).

    Returns:
        The same hook, but an error inside it is logged and turned into a deny.
    """

    @functools.wraps(hook)
    async def guarded(
        hook_input: dict[str, Any], tool_use_id: str | None, context: Any
    ) -> dict[str, Any]:
        try:
            return await hook(hook_input, tool_use_id, context)
        except Exception as error:  # a broken check must block: the SDK would allow on error
            logger.exception("chamber security hook failed; denying the call")
            return deny(
                f"A chamber security check failed ({type(error).__name__}), so this call is "
                "blocked. Try a simpler, more direct form of the command."
            )

    return guarded
