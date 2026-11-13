"""Checks a finished tool by running its verify command (a cheap, read-only command)."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, settings
from signal_setup.registry import Tool

VERIFY_TIMEOUT_S = 120
# Set by `uv run` for setup's own venv; passed on, a nested `uv run --project tools/x` warns
# about it on stderr, and that warning would become the check's detail.
_PARENT_VENV_VARS = ("VIRTUAL_ENV",)


def _child_env() -> dict[str, str]:
    """This process's environment without setup's own venv."""
    return {k: v for k, v in os.environ.items() if k not in _PARENT_VENV_VARS}


def _detail(result: subprocess.CompletedProcess[str]) -> str:
    """The line to show: stdout's last on a pass (stderr may hold warnings), else either's."""
    passed_lines = result.stdout.strip().splitlines() if result.returncode == 0 else []
    lines = passed_lines or (result.stdout + result.stderr).strip().splitlines()
    return lines[-1] if lines else ""


def check(
    root: Path, tool: Tool, data: dict[str, Any], timeout_s: float = VERIFY_TIMEOUT_S
) -> tuple[bool, str]:
    """Placeholders left fail the check; otherwise run the tool's verify command.

    `timeout_s` caps the command (the Tools page passes a short one).

    Returns (passed, last output line or the problem).
    """
    left = settings.tool_leftovers(root, tool, data)
    if left:
        return False, f"placeholders left: {', '.join(left)} (setup config {tool.id})"
    if not tool.verify:
        return True, "nothing to check"
    program = shutil.which(tool.verify[0])
    if program is None:
        return False, f"{tool.verify[0]} isn't available"
    try:
        # The resolved path: Windows only finds .exe files by bare name (see steps/run.py).
        result = subprocess.run(
            [program, *tool.verify[1:]],
            cwd=root,
            env=_child_env(),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout_s:g} s"
    return result.returncode == 0, _detail(result)


def report_line(root: Path, tool: Tool, data: dict[str, Any]) -> str:
    """'OK', 'PROBLEM' or the tool's status, as one line for the end of setup."""
    status = progress.tool_status(data, tool, platforms.current())
    if status != progress.DONE:
        return f"{tool.name}: {status or 'not set up'}"
    passed, detail = check(root, tool, data)
    return f"{tool.name}: {'OK' if passed else 'PROBLEM'} {detail}".rstrip()
