"""Builds the locked-down `claude -p` command line for one run, from its Lockdown.

This is the job's security boundary: the flags, not the prompt, decide what it can
do. Flag names were checked against `claude --help` for Claude Code 2.1.301; the
README's "Lockdown" section has the probes that prove each one.

- --restricted ignores user, project and local settings files (so the repo's
  .claude/settings.local.json `bypassPermissions` default never applies), refuses
  bypassPermissions, and confines file tools to the working directory, life/.
- --permission-mode dontAsk with --permission-prompts none: anything not in the
  allow list is denied, and nobody is asked.
- --tools limits built-in tools to the lockdown's (the digest: Read and Edit; no
  Bash, PowerShell, web, Write, subagents). Edit is allowed only on the exact files
  the runner names for this run. --disallowedTools repeats the dangerous ones and
  removes mail drafting (and, for the digest, mail_accounts and mail_search, which
  the runner now runs itself).
- --strict-mcp-config with the lockdown's MCP config, or none: the digest gets only
  the mail server (no audiohub, browser, sessions, whiteboard or claude.ai connectors).

The lockdown's expected_* values are what claude's init event must report, or the
launcher kills the run before the model acts (init_check.py).
"""

from collections.abc import Iterable
from pathlib import Path

from mail_digest.claude.lockdown import DIGEST_LOCKDOWN, EXPECTED_PERMISSION_MODE, Lockdown


def edit_rules(paths: Iterable[str]) -> list[str]:
    """One exact Edit rule per file (POSIX paths relative to life/).

    The leading / anchors the rule to the working directory, life/. Without it,
    `Edit(inbox.md)` also matches me/inbox.md (a reviewer's probe showed this).
    """
    return [f"Edit(/{path})" for path in paths]


def build_command(
    claude_exe: Path,
    output_schema: str,
    edit_paths: Iterable[str],
    lockdown: Lockdown = DIGEST_LOCKDOWN,
) -> list[str]:
    """The argv for one run. The run context goes in on stdin, not as an argument.

    edit_paths are the only files the run may edit (kb.KbTargets.editable). lockdown
    is the run's tools, rules and MCP config (lockdown.py); the digest's by default.
    Each variadic list (--tools, --allowedTools, --disallowedTools) is followed by
    another flag, so no later value is swallowed into it. An empty --tools stays one
    "" argument, so claude gets no built-in tools at all.
    """
    allowed = [
        *(tool for tool in lockdown.tools if tool != "Edit"),
        *edit_rules(edit_paths),
        *lockdown.extra_allowed,
    ]
    return [
        str(claude_exe),
        "-p",
        "--restricted",
        "--permission-mode", EXPECTED_PERMISSION_MODE,
        "--permission-prompts", "none",
        "--tools", ",".join(lockdown.tools),
        *(["--allowedTools", *allowed] if allowed else []),
        *(["--disallowedTools", *lockdown.disallowed] if lockdown.disallowed else []),
        "--strict-mcp-config",
        *(["--mcp-config", str(lockdown.mcp_config)] if lockdown.mcp_config else []),
        "--append-system-prompt-file", str(lockdown.prompt_path),
        "--json-schema", output_schema,
        "--model", lockdown.model,
        "--max-budget-usd", lockdown.max_budget_usd,
        "--disable-slash-commands",
        "--no-session-persistence",
        "--output-format", "stream-json",
        "--verbose",
    ]  # fmt: skip
