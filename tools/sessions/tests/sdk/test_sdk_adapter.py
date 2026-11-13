"""Tests for build_options (what a managed session launches with) and translate_message."""

import json
from pathlib import Path

import pytest
from claude_agent_sdk import SystemMessage
from support.fakes import assistant_text, result

from claude_sessions.approvals import PermissionModeError
from claude_sessions.sdk import (
    AssistantText,
    LaunchSpec,
    SessionIdentified,
    TurnEnded,
    build_options,
    translate_message,
)

SESSION_ID = "11111111-1111-4111-8111-111111111111"


async def _allow(*_: object) -> None:
    """A can_use_tool stand-in; build_options only stores it."""


def test_options_behave_like_the_owners_normal_sessions(tmp_path: Path) -> None:
    spec = LaunchSpec(tmp_path, "sonnet", "acceptEdits", session_id=SESSION_ID)

    options = build_options(spec, _allow)

    assert options.setting_sources == ["user", "project", "local"]
    assert options.system_prompt == {"type": "preset", "preset": "claude_code"}
    assert options.permission_mode == "acceptEdits"
    assert options.can_use_tool is _allow
    assert (options.cwd, options.model, options.session_id) == (str(tmp_path), "sonnet", SESSION_ID)
    flag_permissions = json.loads(options.settings)["permissions"]
    assert flag_permissions["disableBypassPermissionsMode"] == "disable"
    # Shell readers are denied by name too (aliases such as gc and type included).
    assert "PowerShell(Get-Content *.env*)" in flag_permissions["deny"]
    assert options.env == {"SIGNAL_BRIEF_SURFACE": "managed"}


@pytest.mark.parametrize(
    "secret_path",
    [
        "//**/.env",
        "//**/.env.*",
        "//**/*.env",
        # Mail sign-ins, google_client.json, and the whiteboard, console and sessions tokens.
        "//**/.state/**",
        # The hub's IPC and Spotify tokens.
        "//**/.cache/**",
        "//**/tools/browser/.profile/**",
        "//**/tools/browser/.screenshots/**",
        # The vault store.
        "~/AppData/Local/signal-vault/**",
        "~/.ssh/**",
        "~/.claude/.credentials.json",
        "~/.claude/ide/**",
    ],
)
def test_options_deny_reads_and_writes_of_each_secret_path(
    tmp_path: Path, secret_path: str
) -> None:
    options = build_options(LaunchSpec(tmp_path, None, "default", session_id=SESSION_ID), _allow)

    deny_rules = json.loads(options.settings)["permissions"]["deny"]

    assert {f"Read({secret_path})", f"Edit({secret_path})"} <= set(deny_rules)


def test_options_refuse_bypass_and_need_exactly_one_session_source(tmp_path: Path) -> None:
    with pytest.raises(PermissionModeError):
        build_options(
            LaunchSpec(tmp_path, None, "bypassPermissions", session_id=SESSION_ID), _allow
        )
    with pytest.raises(ValueError, match="exactly one"):
        build_options(LaunchSpec(tmp_path, None, "default"), _allow)
    resumed = build_options(LaunchSpec(tmp_path, None, "plan", resume=SESSION_ID), _allow)
    assert (resumed.resume, resumed.session_id, resumed.model) == (SESSION_ID, None, None)


def test_translation_keeps_main_agent_text_and_turn_outcomes() -> None:
    init = SystemMessage(subtype="init", data={"session_id": SESSION_ID})
    failed = result(SESSION_ID, "", subtype="error_max_turns")

    assert translate_message(init) == [SessionIdentified(SESSION_ID)]
    assert translate_message(assistant_text("pong")) == [AssistantText("pong")]
    assert translate_message(assistant_text("subagent notes", parent_tool_use_id="t1")) == []
    assert translate_message(result(SESSION_ID, "pong", cost=0.5)) == [
        TurnEnded(SESSION_ID, "pong", False, None, 0.5)
    ]
    assert translate_message(failed) == [TurnEnded(SESSION_ID, "", True, "error_max_turns", 0.01)]
