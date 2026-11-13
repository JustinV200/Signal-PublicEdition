"""SdkTurnSession: a ClaudeSDKClient per board change, behind connect/run_turn/disconnect.

The only agent module that imports claude_agent_sdk, so BoardAgent can be
tested with a fake session. The SDK requires every call on a connected
client to come from the task that called connect(); BoardAgent's worker
task does all three.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookMatcher,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import SystemPromptPreset

from whiteboard.agent.permissions import PermissionRouter
from whiteboard.agent.prompt import BOARD_SYSTEM_APPEND

logger = logging.getLogger(__name__)

# "project" loads CLAUDE.md, .claude/settings.json and the repo's .mcp.json (the
# whiteboard and audiohub servers). "local" is left out: its "don't ask again"
# allow rules from interactive sessions would skip can_use_tool. "user" is left
# out so the owner's global model/effort settings don't slow turns.
SETTING_SOURCES = ["project"]
# "default" sends every call the CLI would prompt for to can_use_tool. Never
# bypassPermissions: the agent acts on whatever is written on the board.
PERMISSION_MODE = "default"
# The PreToolUse hook may wait on a 120 s dialog, possibly behind another one.
# The SDK's default hook timeout (60 s) would cut that short.
HOOK_TIMEOUT_S = 300.0
DENIED_MESSAGE = "The owner declined this tool call. Don't retry it."
MS_PER_SECOND = 1000.0
# Tool calls that draw or change the board; a successful one triggers a verify look.
BOARD_CHANGING_TOOLS = frozenset(
    f"mcp__whiteboard__board_{name}" for name in ("draw", "move", "remove", "clear")
)

ClientFactory = Callable[[ClaudeAgentOptions], ClaudeSDKClient]


class SdkTurnSession:
    """One multi-turn Claude Code session for the board agent."""

    def __init__(
        self,
        model: str,
        repo_root: Path,
        router: PermissionRouter,
        client_factory: ClientFactory = ClaudeSDKClient,
    ) -> None:
        """Prepare the session. Nothing starts until connect().

        Args:
            model: Model alias or id; empty means the CLI default.
            repo_root: Working directory for Claude Code.
            router: Decides the tool calls the CLI asks about.
            client_factory: Builds the SDK client; tests pass a fake.
        """
        self._options = build_options(model, repo_root, router)
        self._client_factory = client_factory
        self._client: ClaudeSDKClient | None = None

    async def connect(self) -> None:
        """Start the CLI subprocess.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The CLI couldn't start (e.g. no login).
        """
        client = self._client_factory(self._options)
        await client.connect()
        self._client = client
        logger.info("Board agent session connected (model=%s)", self._options.model or "default")

    async def disconnect(self) -> None:
        """Stop the CLI. Safe to call when not connected."""
        if self._client is None:
            return
        client, self._client = self._client, None
        await client.disconnect()

    async def run_turn(
        self,
        message: dict[str, Any],
        on_first_change: Callable[[], Awaitable[None]] | None = None,
    ) -> bool:
        """Send one user message and wait for the turn to finish.

        Args:
            message: A stream-json user message (see turn_message.py).
            on_first_change: Awaited once, when the first board-changing call succeeds.

        Raises:
            RuntimeError: Not connected.
            claude_agent_sdk.ClaudeSDKError: The CLI failed mid-turn.

        Returns:
            Whether a draw, move, remove or clear call succeeded during the turn.
        """
        if self._client is None:
            raise RuntimeError("The board agent session isn't connected.")
        await self._client.query(_single_message(message))
        pending: set[str] = set()
        changed = False
        async for reply in self._client.receive_response():
            _log_reply(reply)
            just_changed = _track_board_changes(reply, pending)
            if just_changed and not changed and on_first_change is not None:
                await on_first_change()
            changed = just_changed or changed
        return changed


def build_options(model: str, repo_root: Path, router: PermissionRouter) -> ClaudeAgentOptions:
    """Assemble the options for the board agent's ClaudeSDKClient."""
    system_prompt: SystemPromptPreset = {
        "type": "preset",
        "preset": "claude_code",
        "append": BOARD_SYSTEM_APPEND,
    }

    async def can_use_tool(
        tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResult:
        # Backstop only: the PreToolUse hook already decided every call.
        if await router.decide(tool_name, tool_input, context.blocked_path):
            return PermissionResultAllow()
        return PermissionResultDeny(message=DENIED_MESSAGE)

    hook = HookMatcher(matcher=None, hooks=[make_pre_tool_use_hook(router)], timeout=HOOK_TIMEOUT_S)
    return ClaudeAgentOptions(
        cwd=str(repo_root),
        model=model or None,
        system_prompt=system_prompt,
        setting_sources=SETTING_SOURCES,
        permission_mode=PERMISSION_MODE,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [hook]},
        stderr=lambda line: logger.warning("claude cli: %s", line.rstrip()),
    )


def make_pre_tool_use_hook(router: PermissionRouter) -> Any:
    """Make the PreToolUse hook that puts every tool call through the router.

    Hooks run before the CLI's permission rules, so the router's allowlist (and
    its dialog) is authoritative even if a settings file has an allow rule.

    Returns:
        An SDK HookCallback returning an explicit allow or deny decision.
    """

    async def pre_tool_use(
        hook_input: Any, tool_use_id: str | None, context: HookContext
    ) -> dict[str, Any]:
        is_allowed = await router.decide(hook_input["tool_name"], hook_input["tool_input"])
        decision: dict[str, Any] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow" if is_allowed else "deny",
        }
        if not is_allowed:
            decision["permissionDecisionReason"] = DENIED_MESSAGE
        return {"hookSpecificOutput": decision}

    return pre_tool_use


async def _single_message(message: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Wrap one message as the async iterable query() needs for content blocks."""
    yield message


def _track_board_changes(reply: object, pending: set[str]) -> bool:
    """Note board-changing tool calls in `pending`; True when one of them just succeeded."""
    if isinstance(reply, AssistantMessage):
        pending.update(
            b.id
            for b in reply.content
            if isinstance(b, ToolUseBlock) and b.name in BOARD_CHANGING_TOOLS
        )
    elif isinstance(reply, UserMessage) and isinstance(reply.content, list):
        return any(
            isinstance(b, ToolResultBlock) and b.tool_use_id in pending and not b.is_error
            for b in reply.content
        )
    return False


def _log_reply(reply: object) -> None:
    """Log the agent's text and the turn result, so the daemon log shows what it did."""
    if isinstance(reply, AssistantMessage):
        for block in reply.content:
            if isinstance(block, TextBlock) and block.text.strip():
                logger.info("Board agent: %s", block.text.strip())
    elif isinstance(reply, ResultMessage):
        logger.info(
            "Board agent turn done in %.1f s (error=%s, cost=$%s)",
            reply.duration_ms / MS_PER_SECOND,
            reply.is_error,
            reply.total_cost_usd,
        )
