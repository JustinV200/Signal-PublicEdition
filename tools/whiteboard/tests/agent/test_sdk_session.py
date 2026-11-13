"""The board agent's SDK options: its own allowlist is enforced by a PreToolUse hook."""

import pytest

from whiteboard.agent import PermissionRouter
from whiteboard.agent.sdk_session import build_options

pytestmark = pytest.mark.asyncio

HOOK_CONTEXT = {"signal": None}


async def test_the_hook_routes_every_call_through_the_dialog_whatever_settings_allow(
    tmp_path,
) -> None:
    # Regression: allow rules in settings skip can_use_tool, so a "don't ask again"
    # from an interactive session would have let the agent run Bash unasked. The
    # hook runs before those rules, and "local" (where they live) isn't loaded.
    questions: list[str] = []
    router = PermissionRouter(lambda question: questions.append(question) or False)
    options = build_options("haiku", tmp_path, router)
    hook = options.hooks["PreToolUse"][0].hooks[0]

    bash = await hook(
        {"tool_name": "Bash", "tool_input": {"command": "del notes.txt"}}, "t1", HOOK_CONTEXT
    )
    draw = await hook(
        {"tool_name": "mcp__whiteboard__board_draw", "tool_input": {}}, "t2", HOOK_CONTEXT
    )

    assert "local" not in options.setting_sources
    assert options.permission_mode != "bypassPermissions"
    assert bash["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert draw["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert len(questions) == 1 and "Bash" in questions[0]
