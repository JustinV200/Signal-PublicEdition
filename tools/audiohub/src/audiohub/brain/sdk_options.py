"""Builds the claude-agent-sdk options for the voice brain's Claude Code session.

Part of the thin SDK adapter (with sdk_session.py and sdk_tools.py). Only the
sdk_* brain modules import claude_agent_sdk, so the rest of the brain is easy to fake.
"""

import json
import logging
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import (
    CanUseTool,
    ClaudeAgentOptions,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    SettingSource,
    ToolPermissionContext,
)
from claude_agent_sdk.types import EffortLevel, SystemPromptPreset

from audiohub.brain.handoff_tool import HAND_OFF_SERVER, HandOff
from audiohub.brain.permissions import (
    SECRET_READ_DENY_RULES,
    PermissionDecider,
    PermissionRequest,
)
from audiohub.brain.sdk_tools import build_voice_server
from audiohub.brain.voice_prompt import VOICE_SYSTEM_APPEND
from audiohub.config import BrainSettings

logger = logging.getLogger(__name__)

# Which filesystem settings the CLI loads.
# - "project" is what loads CLAUDE.md (and so AGENTS.md), .claude/settings.json
#   and the repo's .mcp.json servers.
# - "local" adds .claude/settings.local.json, where this machine's approvals for
#   .mcp.json servers and local permission rules live. Its `model` and
#   `effortLevel` are the console's pick for new orchestrator sessions; the
#   explicit model and effort below outrank them.
# - "user" (~/.claude/settings.json) is left out on purpose. It sets model "opus"
#   at xhigh effort, and enables user plugins whose MCP servers slow startup.
#   Login credentials are read from ~/.claude regardless of this list.
SETTING_SOURCES: tuple[SettingSource, ...] = ("project", "local")

# "default" sends every tool call the CLI would prompt for to can_use_tool.
PERMISSION_MODE = "default"

# Flag settings outrank every settings file:
# - disableBypassPermissionsMode: no repo or local settings can switch this
#   session into bypassPermissions (tools/sessions sets the same flag).
# - disableClaudeAiConnectors: the account's claude.ai connectors (Gmail send,
#   forward and trash, Docs create and delete) stay out. A misheard "yes" would
#   send mail with no click on the PC, the safeguard the mail server keeps.
# - disableAllHooks: hooks from settings files are skipped, so none can answer
#   "allow" past the gate. The SDK callback hook below still runs.
FLAG_SETTINGS = json.dumps(
    {
        "permissions": {"disableBypassPermissionsMode": "disable"},
        "disableClaudeAiConnectors": True,
        "disableAllHooks": True,
    }
)

# The built-in tools voice gets; MCP tools (the repo's and voice's own, sdk_tools)
# come on top. Every other built-in is left out, above all the agent,
# orchestration, scheduling and remote ones (Agent, SendMessage, ListAgents,
# RemoteTrigger, Workflow, CronCreate, ScheduleWakeup, PushNotification,
# EnterWorktree, DesignSync): SendMessage, for one, reaches the owner's live
# sessions, which may run in bypassPermissions. The hand-off tool reaches only
# the claimed orchestrator. Voice is a thin, fast layer, so it gets no shell,
# file-writing or page-fetching tools: those jobs go to the main session.
# Without ToolSearch the CLI loads MCP tools up front rather than deferring them.
VOICE_TOOLS = ("Read", "Glob", "Grep", "WebSearch")

# MCP tools from the repo's .mcp.json that voice never uses: whole servers
# ("mcp__<server>"), and the write tools of servers it only reads from. As CLI
# deny rules they keep these tools out of voice's context entirely, which keeps
# its prompt short; the gate refuses them anyway, and anything missing here.
HIDDEN_MCP_TOOLS = (
    "mcp__browser",
    "mcp__browser-docker",
    "mcp__mail__mail_draft",
    "mcp__mail__mail_send_draft",
    "mcp__sessions__start_session",
    "mcp__sessions__stop_session",
    "mcp__sessions__send_to_session",
    "mcp__sessions__resume_session",
    "mcp__brief__brief_log",
    "mcp__brief__brief_undo",
)

# The CLI runs some calls without asking can_use_tool: in-project reads, and
# anything a settings allow rule matches. The PreToolUse
# hook below answers "ask" for every tool, so each call reaches the gate, which
# lets the silent ones through itself. CLI deny rules still apply first.
ASK_DECISION = "ask"

# Shown to Claude for a refusal that carries no message of its own.
DEFAULT_REFUSAL_MESSAGE = "Voice can't run this tool call. Don't retry it."


def build_options(
    brain_settings: BrainSettings,
    cwd: Path,
    decide_permission: PermissionDecider,
    hand_off: HandOff,
) -> ClaudeAgentOptions:
    """Assemble the options for the brain's persistent ClaudeSDKClient.

    Args:
        brain_settings: Model and effort, both passed explicitly (see BrainSettings).
        cwd: Working directory for Claude Code, normally the repo root.
        decide_permission: Called for every tool call that deny rules let through.
        hand_off: Runs the hand-off tool (the gate always allows it).

    Returns:
        Options for ClaudeSDKClient.
    """
    system_prompt: SystemPromptPreset = {
        "type": "preset",
        "preset": "claude_code",
        "append": VOICE_SYSTEM_APPEND,
    }
    return ClaudeAgentOptions(
        cwd=str(cwd),
        model=brain_settings.model,
        # Checked against EFFORT_LEVELS on load, all of which are EffortLevel values.
        effort=cast(EffortLevel, brain_settings.effort),
        system_prompt=system_prompt,
        setting_sources=list(SETTING_SOURCES),
        settings=FLAG_SETTINGS,
        tools=list(VOICE_TOOLS),
        # Added to the repo's .mcp.json servers, not instead of them.
        mcp_servers={HAND_OFF_SERVER: build_voice_server(hand_off)},
        permission_mode=PERMISSION_MODE,
        # Deny rules go to this session only, as --disallowedTools, never into
        # a settings file. The secret ones stop a plain read of .env before the
        # gate is asked, as a second layer.
        disallowed_tools=[*SECRET_READ_DENY_RULES, *HIDDEN_MCP_TOOLS],
        can_use_tool=make_can_use_tool(decide_permission),
        # No matcher: the hook runs for every tool.
        hooks={"PreToolUse": [HookMatcher(hooks=[ask_about_every_call])]},
        stderr=_log_cli_stderr,
    )


async def ask_about_every_call(
    hook_input: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PreToolUse hook: tell the CLI to ask about this call, so can_use_tool decides it.

    Args:
        hook_input: The tool call (unused: the gate looks at it instead).
        tool_use_id: The call's id (unused).
        context: The SDK's hook context (unused).

    Returns:
        A PreToolUse "ask" decision.
    """
    return {
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": ASK_DECISION}
    }


def make_can_use_tool(decide_permission: PermissionDecider) -> CanUseTool:
    """Wrap the gate's decider as the SDK's can_use_tool callback.

    Args:
        decide_permission: Returns the gate's decision for a tool call.

    Returns:
        A callback that returns PermissionResultAllow (input unchanged) or
        PermissionResultDeny (without interrupting the turn). The deny message is
        the gate's refusal, or DEFAULT_REFUSAL_MESSAGE when it has none.
    """

    async def can_use_tool(
        tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResult:
        request = PermissionRequest(tool_name, tool_input)
        decision = await decide_permission(request)
        if decision.is_allowed:
            return PermissionResultAllow()
        return PermissionResultDeny(message=decision.refusal or DEFAULT_REFUSAL_MESSAGE)

    return can_use_tool


def _log_cli_stderr(line: str) -> None:
    """Forward the bundled CLI's stderr to our log as a warning.

    The CLI writes to stderr when something is wrong (bad login, failed MCP
    server, crash), and that must be visible without debug logging.
    """
    logger.warning("claude cli: %s", line.rstrip())
