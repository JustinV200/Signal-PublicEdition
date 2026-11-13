"""Tests for mail_digest.claude.launcher: finding claude and the init lockdown check."""

import json
import sys
import time
from pathlib import Path

import pytest

from mail_digest.claude import LaunchOptions, find_claude, launcher, read_events, run_claude

BINARY = "resources/native-binary/claude.exe"
CWD = Path(__file__).parent
GOOD_INIT = {
    "type": "system",
    "subtype": "init",
    "cwd": str(CWD),
    "claude_code_version": "2.1.301",
    "permissionMode": "dontAsk",
    "tools": [
        "Read",
        "Edit",
        "StructuredOutput",
        "mcp__mail__mail_read",
        "mcp__mail__mail_thread",
    ],
    "mcp_servers": [{"name": "mail", "status": "connected"}],
    "additional_directories": [],
}
RESULT = {"type": "result", "subtype": "success"}
# Stand-in claudes: each prints the init event it gets in argv[1], then hangs.
# This one closes stdout first. The timer is cancelled once the output ends, so
# without a kill the run would wait for it.
CLOSES_OUTPUT_AND_HANGS = (
    "import os, sys, time; print(sys.argv[1], flush=True); os.close(1); time.sleep(60)"
)
# This one starts a child that holds its stdout, as an MCP server can. Killing only
# the stand-in at the timeout would leave the child keeping the output open.
HANGS_WITH_A_CHILD_ON_STDOUT = (
    "import subprocess, sys, time; print(sys.argv[1], flush=True); "
    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], stdout=sys.stdout); "
    "time.sleep(60)"
)


def _extension(root, folder):
    path = root / folder / BINARY
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    return path


def _lines(*events):
    return [json.dumps(e) + "\n" for e in events]


def test_prefers_path_then_newest_extension_by_version(tmp_path):
    _extension(tmp_path, "anthropic.claude-code-2.1.99-win32-x64")
    newest = _extension(tmp_path, "anthropic.claude-code-2.1.301-win32-x64")
    (tmp_path / "anthropic.claude-code-2.1.400-win32-x64").mkdir()  # no binary
    assert find_claude(which=lambda _: None, extensions_dir=tmp_path) == newest
    on_path = tmp_path / "bin" / "claude.exe"
    assert find_claude(which=lambda _: str(on_path), extensions_dir=tmp_path) == on_path


def test_matching_init_returns_the_result_event_and_version():
    kills = []
    too_deep = "[" * 100_000 + "]" * 100_000 + "\n"  # json.loads raises RecursionError
    lines = ["not json\n", too_deep, *_lines(GOOD_INIT, RESULT)]
    run = read_events(lines, lambda: kills.append(1), CWD)
    assert run.result == RESULT
    assert run.version == "2.1.301"
    assert not run.error
    assert not kills


@pytest.mark.parametrize(
    "change",
    [
        {"permissionMode": "bypassPermissions"},
        {"tools": [*GOOD_INIT["tools"], "Bash"]},
        {"tools": [*GOOD_INIT["tools"], ["unhashable"]]},  # must not raise TypeError
        {"mcp_servers": [*GOOD_INIT["mcp_servers"], {"name": "audiohub"}]},
        {"additional_directories": ["C:\\"]},
        {"cwd": str(CWD.parent)},
        {"cwd": None},
    ],
)
def test_unexpected_init_kills_the_run(change):
    kills = []
    run = read_events(_lines(dict(GOOD_INIT, **change), RESULT), lambda: kills.append(1), CWD)
    assert kills == [1]
    assert run.result is None
    assert "lockdown check failed" in run.error


def test_a_result_without_an_init_event_is_not_trusted():
    run = read_events(_lines(RESULT), lambda: None, CWD)
    assert run.result is None
    assert "no init event" in run.error


@pytest.mark.parametrize(
    ("stand_in", "timeout_s", "error"),
    [(CLOSES_OUTPUT_AND_HANGS, 120, "no result"), (HANGS_WITH_A_CHILD_ON_STDOUT, 1, "was killed")],
    ids=["closes-output", "child-holds-output"],
)
def test_a_hung_claude_is_killed_and_the_run_returns(
    tmp_path, monkeypatch, stand_in, timeout_s, error
):
    monkeypatch.setattr(launcher, "EXIT_GRACE_S", 1)
    init = json.dumps(dict(GOOD_INIT, cwd=str(tmp_path)))
    options = LaunchOptions(cwd=tmp_path, timeout_s=timeout_s, stderr_path=tmp_path / "stderr.log")
    # A Windows venv's python.exe is a launcher that keeps stdout open for its child,
    # so use the base interpreter (the stand-in needs only the standard library).
    python = getattr(sys, "_base_executable", sys.executable)
    started = time.monotonic()
    run = run_claude([python, "-c", stand_in, init], "context", options)
    assert time.monotonic() - started < 20
    assert error in run.error


def test_a_claude_that_exits_soon_after_its_output_ends_is_not_killed(tmp_path, monkeypatch):
    kills = []
    monkeypatch.setattr(launcher, "kill_tree", lambda *_: kills.append(1))
    init = json.dumps(dict(GOOD_INIT, cwd=str(tmp_path)))
    stand_in = (
        "import os, sys, time; print(sys.argv[1]); print(sys.argv[2], flush=True); "
        "os.close(1); time.sleep(0.5)"
    )
    options = LaunchOptions(cwd=tmp_path, timeout_s=120, stderr_path=tmp_path / "stderr.log")
    python = getattr(sys, "_base_executable", sys.executable)
    run = run_claude([python, "-c", stand_in, init, json.dumps(RESULT)], "context", options)
    assert run.result == RESULT
    assert not kills
