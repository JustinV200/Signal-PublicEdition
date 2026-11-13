"""Tests for mail_digest.claude.command: the lockdown flags are the job's security boundary."""

from pathlib import Path

from mail_digest.claude import build_command

EDITABLE = (
    "inbox.md",
    "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md",
    "terms/2026-fall/courses/hist-205/README.md",
)


def _flag_values(argv: list[str], flag: str) -> list[str]:
    """The values after `flag`, up to the next --flag."""
    start = argv.index(flag) + 1
    values = []
    for arg in argv[start:]:
        if arg.startswith("--"):
            break
        values.append(arg)
    return values


def test_command_locks_the_job_down():
    argv = build_command(Path("claude.exe"), "{}", EDITABLE)
    assert "--restricted" in argv
    assert "--strict-mcp-config" in argv
    assert "--dangerously-skip-permissions" not in argv
    assert _flag_values(argv, "--permission-mode") == ["dontAsk"]
    assert _flag_values(argv, "--permission-prompts") == ["none"]
    assert _flag_values(argv, "--tools") == ["Read,Edit"]
    assert _flag_values(argv, "--output-format") == ["stream-json"]

    allowed = _flag_values(argv, "--allowedTools")
    assert not [t for t in allowed if t.startswith(("Bash", "PowerShell", "Write", "Web"))]
    assert not [t for t in allowed if "draft" in t or "audiohub" in t or "sessions" in t]
    denied = _flag_values(argv, "--disallowedTools")
    # The runner lists and searches the mail itself, so the model can't.
    mail_denied = {"draft", "send_draft", "accounts", "search"}
    assert {"Bash", "PowerShell", *(f"mcp__mail__mail_{t}" for t in mail_denied)} <= set(denied)


def test_edit_is_allowed_only_on_the_exact_anchored_files():
    allowed = _flag_values(build_command(Path("claude.exe"), "{}", EDITABLE), "--allowedTools")
    edits = [t for t in allowed if t.startswith("Edit")]
    # The leading / anchors each rule to life/; without it inbox.md also matches me/inbox.md.
    assert edits == [
        "Edit(/inbox.md)",
        "Edit(/terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md)",
        "Edit(/terms/2026-fall/courses/hist-205/README.md)",
    ]
    assert not [t for t in edits if "*" in t]
