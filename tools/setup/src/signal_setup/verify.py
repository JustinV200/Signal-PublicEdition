"""Checks a finished tool by running its verify command (a cheap, read-only command).

The contract (tools/setup/README.md, "Verify checks"): the exit code says pass or fail,
and the last stdout line may be one JSON object {words, fix, command} (one line each) that
says what was found and how to fix it. Without one, the words are plain (PASS_WORDS /
"check failed"), a failure takes the fix from the tool's registry entry, and its last
output line is kept for `setup verify` only.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, settings
from signal_setup.registry import Tool

VERIFY_TIMEOUT_S = 120
# Set by `uv run` for setup's own venv; passed on, a nested `uv run --project tools/x` warns
# about it on stderr on every check.
_PARENT_VENV_VARS = ("VIRTUAL_ENV",)
# The words for a check that passes without a summary line (never its own output, which
# for some tools is a line of --help text).
PASS_WORDS = "installed"
SUMMARY_KEYS = ("words", "fix", "command")
# A summary field is one short plain line: no C0, DEL or C1 control characters (line
# breaks, tabs, terminal escapes; as the console's setup requests check), at most this
# long stripped.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
MAX_SUMMARY_CHARS = 300


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome; words, fix and command are fields the console's health rows share.

    Attributes:
        passed: The check passed (exit code 0, no placeholders left).
        words: What was found: one short line, a few words or one sentence.
        fix: One sentence on what to do, or None. A passing check may carry one too
            (say "installed but not running").
        command: A full command that fixes it, runnable from the repo root, or None.
        output: For a failed check with no summary line, its last non-empty output line
            (stderr first), so `setup verify` can show the error; else None. Never a row's
            words: for some tools it's a line of help text.
    """

    passed: bool
    words: str
    fix: str | None = None
    command: str | None = None
    output: str | None = None


def _child_env() -> dict[str, str]:
    """This process's environment without setup's own venv, with UTF-8 output."""
    env = {k: v for k, v in os.environ.items() if k not in _PARENT_VENV_VARS}
    # A Python check prints UTF-8 even where the locale can't (cp1252 has no emoji).
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _summary(stdout: str) -> dict[str, str | None] | None:
    """The {words, fix, command} object on stdout's last line, or None if there isn't one.

    The check is another program's output, so anything but an object whose `words` is a
    non-blank string (and whose fix and command are strings or null), each one plain line
    of at most MAX_SUMMARY_CHARS, counts as no summary. One line each: a copied multi-line
    command would run more than one command. Fields are stripped; a blank fix or command
    is None.
    """
    lines = stdout.strip().splitlines()
    try:
        payload = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    summary: dict[str, str | None] = {}
    for key in SUMMARY_KEYS:
        value = payload.get(key)
        if value is None:
            summary[key] = None
        elif _is_plain_line(value):
            summary[key] = value.strip() or None
        else:
            return None
    return summary if summary["words"] else None


def _is_plain_line(value: object) -> bool:
    """True for a string with no control characters, at most MAX_SUMMARY_CHARS once stripped."""
    return (
        isinstance(value, str)
        and not _CONTROL.search(value)
        and len(value.strip()) <= MAX_SUMMARY_CHARS
    )


def _last_line(text: str) -> str | None:
    """The last non-empty line of `text`, stripped, or None."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else None


def _result(tool: Tool, done: subprocess.CompletedProcess[str]) -> CheckResult:
    """The check's outcome from its exit code and its summary line, if any."""
    passed = done.returncode == 0
    summary = _summary(done.stdout)
    # A failure without a summary keeps its error line for `setup verify` (stderr first).
    output = None
    if summary is None and not passed:
        output = _last_line(done.stderr) or _last_line(done.stdout)
    summary = summary or {}
    plain_words = PASS_WORDS if passed else f"check failed (exit {done.returncode})"
    # A summary's fix stands on a pass too ("installed but not running"); the registry's
    # fix fills in only for a failure the check didn't explain itself.
    fix = summary.get("fix") or (None if passed else tool.fix)
    words = summary.get("words") or plain_words
    return CheckResult(passed, words, fix, summary.get("command"), output)


def check(
    root: Path, tool: Tool, data: dict[str, Any], timeout_s: float = VERIFY_TIMEOUT_S
) -> CheckResult:
    """Placeholders left fail the check; otherwise run the tool's verify command.

    `timeout_s` caps the command (the System Tools list passes a short one). Never raises for
    a failing check: a missing program or a timeout is a failed result.
    """
    left = settings.tool_leftovers(root, tool, data)
    if left:
        return CheckResult(
            False,
            f"placeholders left: {', '.join(left)}",
            "Fill them in with setup config.",
            f"uv run --project tools/setup --frozen setup config {tool.id}",
        )
    if not tool.verify:
        return CheckResult(True, "nothing to check")
    program = shutil.which(tool.verify[0])
    if program is None:
        return CheckResult(False, f"{tool.verify[0]} isn't available", tool.fix)
    try:
        # The resolved path: Windows only finds .exe files by bare name (see steps/run.py).
        done = subprocess.run(
            [program, *tool.verify[1:]],
            cwd=root,
            env=_child_env(),
            capture_output=True,
            # Not the locale (cp1252 here): a character it can't decode must not raise.
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(False, f"timed out after {timeout_s:g} s", tool.fix)
    return _result(tool, done)


def report_line(root: Path, tool: Tool, data: dict[str, Any]) -> str:
    """'OK', 'PROBLEM' or the tool's status, as one line for the end of setup."""
    status = progress.tool_status(data, tool, platforms.current())
    if status != progress.DONE:
        return f"{tool.name}: {status or 'not set up'}"
    result = check(root, tool, data)
    line = f"{tool.name}: {'OK' if result.passed else 'PROBLEM'} {result.words}"
    if result.fix:
        line += f" Fix: {result.fix}"
    if result.command:
        line += f" Run: {result.command}"
    return line
