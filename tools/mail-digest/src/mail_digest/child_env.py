"""How the runner starts child processes: a clean environment, no window.

Used by claude/launcher.py (claude itself, and kill_tree for its every kill), through
run_hidden by announce/notify.py (the audiohub CLI), steps/todo_board.py (the
whiteboard CLI), digest_email/send.py (the mail CLI) and assignment_check/visit.py
(browser-tool-visit, Edge included in the tree kill), and through run_hidden_output by
kb/review.py (git).
"""

import contextlib
import logging
import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import IO

from mail_digest.settings import REPO_ROOT

log = logging.getLogger(__name__)

# Variables a parent Claude Code session sets for its own children. Passed on, they
# make the job act as that session's child (a messaging pipe back into it,
# non-blocking MCP start-up). The scheduled task never has them; a hand run from
# inside a Claude session would.
INHERITED_SESSION_VARS = ("CLAUDECODE", "CLAUDE_PID", "MCP_CONNECTION_NONBLOCKING")
INHERITED_SESSION_PREFIXES = ("CLAUDE_CODE_", "CLAUDE_AGENT_SDK_")

# Keeps a child (and anything it starts) from opening a console window when the
# runner itself has none (the scheduled task runs pythonw).
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# How much of a helper CLI's error output to keep in the log.
ERROR_TAIL_CHARS = 300
# How long to wait for taskkill, and for a helper CLI to exit after the kill.
KILL_WAIT_S = 5
# taskkill's exit code when the process is already gone (nothing left to kill).
TASKKILL_NOT_FOUND = 128
# A Python CLI writing to a file uses the locale's code page (cp1252) unless told
# otherwise, and _text decodes its output as UTF-8, so email text with accents,
# dashes or emoji would come back garbled.
UTF8_OUTPUT_ENV = {"PYTHONIOENCODING": "utf-8"}
# By full path, so a taskkill.exe in the cwd or on PATH can't stand in for it.
TASKKILL = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "taskkill.exe"


def clean_env(environ: Mapping[str, str]) -> dict[str, str]:
    """A copy of environ without a parent Claude session's variables."""
    return {
        name: value
        for name, value in environ.items()
        if name not in INHERITED_SESSION_VARS and not name.startswith(INHERITED_SESSION_PREFIXES)
    }


def run_hidden(name: str, argv: list[str], timeout_s: int) -> bool:
    """Run a helper CLI once: no window, clean env, repo-root cwd. True only on exit 0.

    name labels it in the log. argv is a list, so no shell parses it. Never raises:
    a CLI that can't start (its output files included), times out or fails is logged
    (with its stderr's tail).
    """
    return run_hidden_output(name, argv, timeout_s) is not None


def run_hidden_output(name: str, argv: list[str], timeout_s: int) -> str | None:
    """Like run_hidden, but returns the CLI's stdout as text on exit 0, else None.

    At the timeout the CLI's whole process tree is killed (uv run's python child
    outlives a plain kill), and its output goes to temp files rather than pipes, so
    nothing waits on a pipe that a leftover child still holds (subprocess.run's
    communicate() would).
    """
    # The try is outside the with, so temp files that can't be made (a full or
    # unwritable temp folder) are logged too, not raised.
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                cwd=REPO_ROOT,
                env={**clean_env(os.environ), **UTF8_OUTPUT_ENV},
                creationflags=CREATE_NO_WINDOW,
            )
            try:
                exit_code = process.wait(timeout_s)
            except subprocess.TimeoutExpired:
                log.warning("%s ran past %d s and was killed", name, timeout_s)
                kill_tree(name, process)
                return None
            if exit_code != 0:
                log.warning("%s exited %d: %s", name, exit_code, _tail(stderr))
                return None
            return _text(stdout)
    except OSError as error:
        log.warning("%s didn't run, or its output couldn't be read: %s", name, error)
        return None


def kill_tree(name: str, process: subprocess.Popen) -> None:
    """Kill process and every process under it, then reap it without blocking on it.

    name labels it in the log. Never raises: a taskkill that fails is logged, and
    the process itself is still killed.
    """
    # taskkill /T finds the children by their parent's pid, so it runs first, while
    # that pid is still alive.
    taskkill = [str(TASKKILL), "/T", "/F", "/PID", str(process.pid)]
    try:
        subprocess.run(
            taskkill,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=KILL_WAIT_S,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        # Not found means it exited by itself just before the kill: not a problem.
        level = logging.DEBUG if error.returncode == TASKKILL_NOT_FOUND else logging.WARNING
        log.log(level, "taskkill couldn't end %s's process tree: %s", name, error)
    except (OSError, subprocess.SubprocessError) as error:
        log.warning("taskkill couldn't end %s's process tree: %s", name, error)
    process.kill()  # in case taskkill didn't (a no-op if it's gone)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(KILL_WAIT_S)


def _text(output: IO[bytes]) -> str:
    """A finished CLI's whole output file, as text."""
    output.seek(0)
    return output.read().decode("utf-8", errors="replace")


def _tail(output: IO[bytes]) -> str:
    """The last ERROR_TAIL_CHARS of a finished CLI's output file, as text."""
    return _text(output).strip()[-ERROR_TAIL_CHARS:]
