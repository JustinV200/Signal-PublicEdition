"""Tests for the voice permission gate: voice's own quick tools run, everything else is refused."""

import logging
import os
from pathlib import Path

import pytest

from audiohub.brain.handoff_tool import HAND_OFF_TOOL_NAME
from audiohub.brain.permissions import (
    PermissionDecision,
    PermissionGate,
    PermissionRequest,
    is_auto_allowed,
)
from audiohub.brain.permissions.gate import MAIN_SESSION_HANDOFF_MESSAGE
from audiohub.brain.permissions.secret_paths import SECRET_READ_REFUSAL
from audiohub.config import BrainSettings

SETTINGS = BrainSettings()
SERVERS = SETTINGS.auto_allow_mcp_servers
PROJECT = Path(r"C:\src\Signal")
HOME_FILE = os.path.join("~", "Documents", "plan.txt")
HOME_CREDENTIALS = os.path.join("~", ".claude", ".credentials.json")
HOME_VAULT = os.path.join("~", "AppData", "Local", "signal-vault", "store.json")
HOME_GH_TOKEN = os.path.join("~", ".config", "gh", "hosts.yml")
HOME_TRANSCRIPT = os.path.join("~", ".claude", "projects", "c--src-Signal", "a.jsonl")

ALLOWED = PermissionDecision(True)
HANDED_OFF = PermissionDecision(False, refusal=MAIN_SESSION_HANDOFF_MESSAGE)
SECRET_REFUSED = PermissionDecision(False, refusal=SECRET_READ_REFUSAL)


def call(tool_name: str, **tool_input: object) -> PermissionRequest:
    return PermissionRequest(tool_name, tool_input)


@pytest.mark.parametrize(
    ("tool_name", "servers", "expected"),
    [
        ("Read", SERVERS, True),
        ("read", SERVERS, False),  # tool names are exact
        ("mcp__audiohub__music_set_volume", SERVERS, True),
        ("mcp__whiteboard__board_draw", ("audiohub",), False),  # servers come from the config
        ("mcp____notify", ("",), False),  # a blank server name allows nothing
        # Look-alike MCP names.
        ("mcp__audiohubx__notify", SERVERS, False),
        ("mcp__audiohub___notify", SERVERS, False),  # server "audiohub_"
        ("mcp__audiohub__evil__notify", SERVERS, False),  # server "audiohub__evil"
        ("mcp__audiohub__", SERVERS, False),  # no tool name
    ],
)
def test_is_auto_allowed(tool_name: str, servers: tuple[str, ...], expected: bool) -> None:
    assert is_auto_allowed(tool_name, SETTINGS.auto_allow_tools, servers) is expected


# The security table with the default config: allowed silently, refused as a job
# for the main session, or refused as a secret. Nothing is ever asked.
GATE_CASES: list[tuple[PermissionRequest, PermissionDecision]] = [
    # Voice's own quick tools.
    (call("Read", file_path=HOME_FILE), ALLOWED),
    (call("Read", file_path=".claude/settings.json"), ALLOWED),
    (call("Grep", pattern="token", path="src"), ALLOWED),
    (call("WebSearch", query="weather"), ALLOWED),
    (call("mcp__audiohub__music_play"), ALLOWED),
    (call("mcp__whiteboard__board_draw"), ALLOWED),
    (call("mcp__brief__brief_me"), ALLOWED),
    (call("mcp__brief__away_on"), ALLOWED),
    (call("mcp__sleepmode__sleep_mode_on"), ALLOWED),
    (call("mcp__mail__mail_search", query="rent"), ALLOWED),
    (call("mcp__mail__mail_read", account="personal", id="m1"), ALLOWED),
    (call("mcp__sessions__session_status", id="s1"), ALLOWED),
    (call("mcp__sessions__list_sessions"), ALLOWED),
    # The hand-off runs without a question.
    (call(HAND_OFF_TOOL_NAME, job="Fix the loader."), ALLOWED),
    # Everything else is the main session's job: shell, writes, fetching, the
    # browsers, sending mail, driving sessions, unknown tools.
    (call("Bash", command="git status"), HANDED_OFF),
    (call("PowerShell", command='Invoke-Item "hw3 notes.docx"'), HANDED_OFF),
    (call("Edit", file_path="life/notes.md", old_string="a", new_string="b"), HANDED_OFF),
    (call("Write", file_path="life/notes.md"), HANDED_OFF),
    (call("NotebookEdit", notebook_path="a.ipynb"), HANDED_OFF),
    (call("WebFetch", url="https://example.com/", prompt="?"), HANDED_OFF),
    (call("mcp__browser__navigate", url="https://lms.example.edu/"), HANDED_OFF),
    (call("mcp__browser-docker__navigate", url="https://example.com/"), HANDED_OFF),
    (call("mcp__mail__mail_draft", to="a@b.c"), HANDED_OFF),
    (call("mcp__mail__mail_send_draft", account="personal", draft_id="d1"), HANDED_OFF),
    (call("mcp__sessions__start_session", repo="mail", prompt="x"), HANDED_OFF),
    (call("mcp__sessions__send_to_session", id="s1", prompt="x"), HANDED_OFF),
    (call("mcp__sessions__stop_session", id="s1"), HANDED_OFF),
    (call("mcp__brief__brief_log", text="x"), HANDED_OFF),  # injected text can't log
    (call("mcp__brief__brief_undo"), HANDED_OFF),
    (call("mcp__github__create_issue"), HANDED_OFF),
    (call("Agent", prompt="x"), HANDED_OFF),
    # Secret reads, however they're spelled, are refused.
    (call("Read", file_path="tools/mail/.state/x.json"), SECRET_REFUSED),
    (call("Read", file_path=".env."), SECRET_REFUSED),
    (call("Read", file_path="tools/mail/.ENV"), SECRET_REFUSED),  # any case
    (call("Read", file_path=HOME_TRANSCRIPT), SECRET_REFUSED),
    (call("Read", file_path="tools/audiohub/.cache/ipc-token"), SECRET_REFUSED),
    (call("Grep", pattern="x", path="tools/browser/.screenshots"), SECRET_REFUSED),
    (call("Glob", pattern="~/.ssh/*"), SECRET_REFUSED),
    (call("Read", file_path=HOME_CREDENTIALS), SECRET_REFUSED),
    (call("Read", file_path=HOME_VAULT), SECRET_REFUSED),
    (call("Read", file_path=HOME_GH_TOKEN), SECRET_REFUSED),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_call", "expected"), GATE_CASES)
async def test_gate_allows_or_refuses(
    tool_call: PermissionRequest, expected: PermissionDecision
) -> None:
    gate = PermissionGate(SETTINGS.auto_allow_tools, PROJECT, auto_allow_mcp_servers=SERVERS)
    assert await gate.decide(tool_call) == expected


@pytest.mark.asyncio
async def test_allowed_calls_are_logged_with_their_resolved_paths(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = PermissionGate(SETTINGS.auto_allow_tools, PROJECT)
    caplog.set_level(logging.INFO, logger="audiohub.brain.permissions.gate")
    readme = r"C:\src\Signal\life\README.md"
    await gate.decide(call("Read", file_path=readme))
    [record] = caplog.records
    assert "Read" in record.getMessage() and readme in record.getMessage()


@pytest.mark.asyncio
async def test_a_secret_folder_reached_through_a_junction_is_refused(
    tmp_path: Path, make_junction
) -> None:
    # The CLI's deny rules read the path as written; the gate resolves it first.
    project = tmp_path / "Signal"
    project.mkdir()
    make_junction(project / "notes", project / "tools" / "mail" / ".state")
    gate = PermissionGate(SETTINGS.auto_allow_tools, project)
    decision = await gate.decide(call("Read", file_path="notes/token.json"))
    assert decision == SECRET_REFUSED
