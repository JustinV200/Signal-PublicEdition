"""Security tables for the send block: layer 1 lists and the deny-by-default hook."""

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import (
    allowed_mcp_tools,
    disallowed_tools,
    mcp_servers_for,
    send_block_hook,
)
from analysis_chamber.security.rules.tool_lists import OUTBOUND_TOOLS, SIGNAL_SERVER_TOOLS
from analysis_chamber.security.send_block import block_reason, matches_entry

ROLES = ["lead", "critic", "qa", "signup"]

# Every outbound or destructive tool across Signal's MCPs, the claude.ai connectors and
# the built-ins. Each must be denied for every role by both layers.
OUTBOUND = [
    "WebFetch",
    "WebSearch",
    "SendMessage",
    "Artifact",
    "ArtifactCheck",
    "SendFile",
    "SendUserMessage",
    "SendUserFile",
    "PushNotification",
    "RemoteTrigger",
    "PublishPlugin",
    "CronCreate",
    "ScheduleWakeup",
    "Monitor",
    "mcp__mail__mail_draft",
    "mcp__mail__mail_send_draft",
    "mcp__rcs__rcs_send",
    "mcp__rcs__rcs_send_message",
    "mcp__brief__brief_log",
    "mcp__brief__brief_resolve",
    "mcp__brief__brief_ack",
    "mcp__brief__brief_me",
    "mcp__brief__away_on",
    "mcp__sessions__start_session",
    "mcp__sessions__send_to_session",
    "mcp__browser__upload_file",
    "mcp__browser__fill_login",
    "mcp__browser-docker__upload_file",
    "mcp__audiohub__notify",
    "mcp__audiohub__music_play",
    "mcp__whiteboard__board_draw",
    "mcp__whiteboard__board_clear",
    "mcp__sleepmode__sleep_mode_on",
    "mcp__claude_ai_Gmail__send_message",
    "mcp__claude_ai_Gmail__reply",
    "mcp__claude_ai_Gmail__forward",
    "mcp__claude_ai_Gmail__create_draft",
    "mcp__claude_ai_Gmail__trash_thread",
    "mcp__claude_ai_Google_Calendar__create_event",
    "mcp__claude_ai_Google_Calendar__delete_event",
    "mcp__claude_ai_Google_Calendar__respond_to_event",
    "mcp__claude_ai_Claude_Docs__create",
    "mcp__claude_ai_Google_Drive__create_file",
    "mcp__claude_ai_Some_Future_Connector__post",
    "mcp__analysis-chamber__chamber_start",
]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("tool", OUTBOUND)
def test_outbound_tools_denied_by_both_layers(role: str, tool: str) -> None:
    assert any(matches_entry(tool, entry) for entry in disallowed_tools(role))
    assert block_reason(role, tool, {}) is not None


# (role, tool, tool input, allowed?): the deny-by-default allowlists.
ALLOWLIST_TABLE = [
    ("lead", "mcp__mail__mail_read", {"account": "personal"}, True),
    ("lead", "mcp__rcs__rcs_search", {}, True),
    ("lead", "mcp__chamber__chamber_fetch", {}, True),
    ("lead", "Bash", {}, True),
    ("lead", "mcp__browser__navigate", {}, False),
    ("lead", "mcp__sessions__list_sessions", {}, False),
    ("lead", "mcp__rcs__rcs_new_tool", {}, False),  # unknown tool on an allowed server
    ("lead", "mcp__someplugin__anything", {}, False),
    ("critic", "mcp__mail__mail_read", {"account": "personal"}, False),
    ("qa", "mcp__chamber__chamber_extract_file", {}, True),
    ("signup", "mcp__browser__navigate", {}, True),
    ("signup", "mcp__mail__mail_search", {"account": "signup@example.test"}, True),
    ("signup", "mcp__mail__mail_search", {"account": "personal"}, False),
    ("signup", "mcp__mail__mail_accounts", {}, True),
    ("signup", "Bash", {}, False),
    ("signup", "PowerShell", {}, False),
]


@pytest.mark.parametrize(("role", "tool", "tool_input", "allowed"), ALLOWLIST_TABLE)
def test_layer_two_allowlist(role: str, tool: str, tool_input: dict, allowed: bool) -> None:
    assert (block_reason(role, tool, tool_input, "signup@example.test") is None) is allowed


def test_signup_reads_no_mail_account_when_none_is_configured() -> None:
    reason = block_reason("signup", "mcp__mail__mail_search", {"account": ""})
    assert reason is not None


@pytest.mark.parametrize("role", ROLES)
def test_layer_one_denies_every_known_tool_off_the_allowlist(role: str) -> None:
    allowed = set(allowed_mcp_tools(role))
    assert allowed.isdisjoint(OUTBOUND_TOOLS)
    entries = disallowed_tools(role)
    for server, tools in SIGNAL_SERVER_TOOLS.items():
        for tool in tools:
            name = f"mcp__{server}__{tool}"
            assert (name in allowed) is not any(matches_entry(name, e) for e in entries), name
    assert mcp_servers_for(role) == {name.split("__")[1] for name in allowed}


@pytest.mark.asyncio
async def test_hook_denies_send_under_bypass() -> None:
    sent = await send_block_hook(
        hook_input("mcp__mail__mail_send_draft", account="personal", draft_id="d"),
        "u",
        {},
        role="lead",
    )
    read = await send_block_hook(hook_input("mcp__mail__mail_read"), "u", {}, role="lead")
    assert is_deny(sent)
    assert read == {}
