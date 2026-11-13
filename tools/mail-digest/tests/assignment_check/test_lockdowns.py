"""The checker's two lockdowns: the reader's and writer's argvs, and the init checks that
kill a run whose claude loaded more than its lockdown allows."""

from pathlib import Path

import pytest

from mail_digest.assignment_check.reader import READER_LOCKDOWN, reader_command
from mail_digest.assignment_check.writer import WRITER_LOCKDOWN, writer_command
from mail_digest.claude import init_problems

CLAUDE = Path("claude.exe")
EDITABLE = ("inbox.md", "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md")


def _values(argv, flag):
    """The values after flag, up to the next --flag."""
    values = []
    for arg in argv[argv.index(flag) + 1 :]:
        if arg.startswith("--"):
            break
        values.append(arg)
    return values


def test_the_reader_gets_no_tools_and_no_servers():
    argv = reader_command(CLAUDE)
    tools_at = argv.index("--tools")
    # "" is its own argument, followed straight away by another flag.
    assert argv[tools_at + 1] == "" and argv[tools_at + 2].startswith("--")
    assert {"--restricted", "--strict-mcp-config"} <= set(argv)
    assert not {"--mcp-config", "--allowedTools", "--dangerously-skip-permissions"} & set(argv)
    assert _values(argv, "--permission-mode") == ["dontAsk"]
    assert _values(argv, "--max-budget-usd") == ["1.00"]


def test_the_writer_gets_read_and_exact_edits_and_no_servers():
    argv = writer_command(CLAUDE, EDITABLE)
    assert _values(argv, "--tools") == ["Read,Edit"]
    assert _values(argv, "--allowedTools") == [
        "Read",
        "Edit(/inbox.md)",
        "Edit(/terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md)",
    ]
    assert {"Bash", "Write", "mcp__mail__mail_draft"} <= set(_values(argv, "--disallowedTools"))
    assert "--strict-mcp-config" in argv and "--mcp-config" not in argv


def _init(tools, servers=(), mode="dontAsk", cwd="."):
    return {"permissionMode": mode, "tools": list(tools), "mcp_servers": list(servers), "cwd": cwd}


MAIL = {"name": "mail", "status": "connected"}


@pytest.mark.parametrize(
    ("lockdown", "event", "is_ok"),
    [
        (READER_LOCKDOWN, _init(["StructuredOutput"]), True),
        (READER_LOCKDOWN, _init(["StructuredOutput", "Read"]), False),
        (READER_LOCKDOWN, _init(["StructuredOutput"], [MAIL]), False),
        (READER_LOCKDOWN, _init(["StructuredOutput"], mode="default"), False),
        (WRITER_LOCKDOWN, _init(["Read", "Edit", "StructuredOutput"]), True),
        (WRITER_LOCKDOWN, _init(["Read", "Edit", "StructuredOutput", "Bash"]), False),
        (WRITER_LOCKDOWN, _init(["Read", "Edit", "StructuredOutput"], [MAIL]), False),
        (WRITER_LOCKDOWN, _init(["Read", "Edit", "StructuredOutput"], mode="acceptEdits"), False),
    ],
    ids=[
        "reader-ok",
        "reader-extra-tool",
        "reader-mcp-server",
        "reader-wrong-mode",
        "writer-ok",
        "writer-extra-tool",
        "writer-mcp-server",
        "writer-wrong-mode",
    ],
)
def test_init_check_kills_a_run_with_more_than_its_lockdown(lockdown, event, is_ok):
    assert (init_problems(event, Path("."), lockdown) == []) is is_ok
