"""Tests for the ClaudeAgentOptions the brain builds and its can_use_tool wrapper."""

import json
from pathlib import Path

import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from audiohub.brain.permissions import (
    SECRET_READ_DENY_RULES,
    PermissionDecision,
    PermissionRequest,
)
from audiohub.brain.sdk_options import DEFAULT_REFUSAL_MESSAGE, build_options, make_can_use_tool
from audiohub.config import BrainSettings

REPO_ROOT = Path(r"C:\src\Signal")


async def allow_everything(request: PermissionRequest) -> PermissionDecision:
    return PermissionDecision(True)


async def hand_off_nowhere(job: str) -> str:
    return "not sent"


@pytest.mark.asyncio
async def test_security_options_send_every_call_to_the_gate() -> None:
    options = build_options(BrainSettings(), REPO_ROOT, allow_everything, hand_off_nowhere)
    assert options.permission_mode == "default"
    assert options.can_use_tool is not None
    # Auto-allow happens in our callback, not in the CLI's allow list.
    assert options.allowed_tools == []
    assert set(SECRET_READ_DENY_RULES) <= set(options.disallowed_tools)
    assert "mcp__browser" in options.disallowed_tools  # never enters voice's context
    # No bypass mode, no claude.ai connectors (Gmail send), no settings-file hooks.
    assert json.loads(options.settings or "{}") == {
        "permissions": {"disableBypassPermissionsMode": "disable"},
        "disableClaudeAiConnectors": True,
        "disableAllHooks": True,
    }
    # A hook on every tool answering "ask" stops the CLI running "safe" shell
    # commands, or allow-rule matches, without can_use_tool.
    [matcher] = (options.hooks or {})["PreToolUse"]
    assert matcher.matcher is None
    [hook] = matcher.hooks
    hook_input = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell", "tool_input": {}}
    output = await hook(hook_input, "tool-1", {"signal": None})
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert isinstance(options.tools, list)
    assert set(options.tools) == {"Read", "Glob", "Grep", "WebSearch"}  # no shell or writes
    assert "SendMessage" not in options.tools
    # Voice's own hand-off tool rides on top of the repo's .mcp.json servers.
    assert isinstance(options.mcp_servers, dict)
    assert set(options.mcp_servers) == {"voice"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "message"),
    [
        (PermissionDecision(False), DEFAULT_REFUSAL_MESSAGE),
        (PermissionDecision(False, refusal="hand it off"), "hand it off"),
    ],
)
async def test_can_use_tool_denies_with_the_gates_message_without_interrupting(
    decision: PermissionDecision, message: str
) -> None:
    async def decider(request: PermissionRequest) -> PermissionDecision:
        return decision

    result = await make_can_use_tool(decider)("Read", {"file_path": "x"}, ToolPermissionContext())
    assert isinstance(result, PermissionResultDeny)
    assert result.message == message
    assert result.interrupt is False


@pytest.mark.asyncio
async def test_can_use_tool_passes_the_request_on_and_allows_with_input_unchanged() -> None:
    seen: list[PermissionRequest] = []

    async def recording_decider(request: PermissionRequest) -> PermissionDecision:
        seen.append(request)
        return PermissionDecision(True)

    context = ToolPermissionContext()
    result = await make_can_use_tool(recording_decider)("Read", {"file_path": "id_rsa"}, context)
    assert seen == [PermissionRequest("Read", {"file_path": "id_rsa"})]
    assert isinstance(result, PermissionResultAllow)
    assert result.updated_input is None
