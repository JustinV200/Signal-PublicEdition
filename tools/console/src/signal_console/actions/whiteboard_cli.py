"""Run one `whiteboard` CLI command for a console button and return its output.

The CLI is what the board_* MCP tools and the owner's terminal use: it finds (or
starts) the daemon and sends the request with the daemon's token, and the
task grid is drawn by its client-side code. Running it as a subprocess with an
argument list (never a shell) keeps that in one place. Its error line
(`whiteboard: error: ...`) or its own failure line becomes the error the
console shows.

On a timeout, or when the server cancels the action (shutdown), the CLI's own
process tree is killed, so a calibrate can't keep running after the button's
lock is freed. A whiteboard daemon the CLI just started is left running: it is
a descendant too, but it's meant to outlive the command that started it.
"""

import asyncio
import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Sequence

import psutil

from signal_console.launch import CREATE_NO_WINDOW, clean_env
from signal_console.paths import REPO_ROOT
from signal_console.process_tree import kill_processes, owned_tree

# As in .mcp.json, from the repo root, so a daemon a button starts gets the same .env.
# --no-sync: the venv is synced separately; a sync here fails on Windows when
# whiteboard.exe is in use (MCP servers, the daemon) and broke every button.
WHITEBOARD_ARGS = (
    "run",
    "--env-file",
    ".env",
    "--project",
    "tools/whiteboard",
    "--frozen",
    "--no-sync",
    "whiteboard",
)
# How the CLI starts the daemon (whiteboard's daemon_client/connection.py):
# `<python> -m whiteboard.cli serve`. Those words in a command line mark the daemon.
DAEMON_ARGS = ("whiteboard.cli", "serve")
# A calibrate (and starting the daemon first) takes well under this; the page
# stops showing the button as working after 2 minutes (web PENDING_MAX_MS).
TIMEOUT_S = 110.0
ERROR_PREFIX = "whiteboard: error:"
MAX_ERROR_CHARS = 400
# The output carries board text; never let a narrow code page mangle it.
ENCODING_ENV = {"PYTHONIOENCODING": "utf-8"}

log = logging.getLogger(__name__)


class StepFailed(RuntimeError):
    """A console action's step failed; the message is what the console shows."""


async def run_whiteboard(args: Sequence[str], base_command: Sequence[str] | None = None) -> str:
    """Run `whiteboard <args>` from the repo root and return its stdout.

    Args:
        args: The fixed arguments after `whiteboard`.
        base_command: The program to run instead of `uv run ... whiteboard` (tests).

    Raises:
        StepFailed: uv is missing, it couldn't start, it timed out, or it exited
            non-zero (the CLI's error).
        asyncio.CancelledError: The action was cancelled; the CLI was killed first.
    """
    process = await _start([*(base_command or _uv_whiteboard()), *args])
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), TIMEOUT_S)
    except TimeoutError as error:
        await _kill(process)
        raise StepFailed(f"the whiteboard didn't finish within {TIMEOUT_S:g} s") from error
    except asyncio.CancelledError:
        await _kill(process)
        raise
    out, err = _text(stdout), _text(stderr)
    if process.returncode != 0:
        log.warning("whiteboard %s exited %s: %s", list(args), process.returncode, err)
        raise StepFailed(_failure_text(out, err, process.returncode))
    return out


async def _start(command: list[str]) -> asyncio.subprocess.Process:
    try:
        return await asyncio.create_subprocess_exec(
            *command,
            cwd=REPO_ROOT,
            env=clean_env(os.environ) | ENCODING_ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # The server has no console window; without this each run would open one.
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError as error:
        raise StepFailed(f"couldn't start the whiteboard command: {error}") from error


async def _kill(process: asyncio.subprocess.Process) -> None:
    """Kill the CLI's own process tree (not a daemon it started) and reap it."""
    try:
        tree = owned_tree(psutil.Process(process.pid), _is_not_daemon)
        # kill_processes waits for the exits, so it runs off the event loop.
        alive = await asyncio.to_thread(kill_processes, tree)
    except psutil.NoSuchProcess:
        alive = []  # It finished on its own.
    except psutil.Error as error:
        log.warning("couldn't kill the whiteboard command (pid %s): %s", process.pid, error)
        with contextlib.suppress(ProcessLookupError):  # Already gone.
            process.kill()
        alive = []
    if alive:
        log.warning("whiteboard command processes still running after the kill: %s", alive)
    await process.wait()


def _is_not_daemon(process: psutil.Process) -> bool:
    # False for the daemon (left running with everything under it), and for a
    # process that can't be inspected: it isn't provably ours, so it's left alone.
    try:
        command_line = process.cmdline()
    except psutil.Error:
        return False
    pairs = zip(command_line, command_line[1:], strict=False)
    return DAEMON_ARGS not in pairs


def _uv_whiteboard() -> list[str]:
    uv = shutil.which("uv")
    if uv is None:
        raise StepFailed("uv isn't on PATH")
    return [uv, *WHITEBOARD_ARGS]


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


def _failure_text(out: str, err: str, code: int | None) -> str:
    # The CLI's own error line if it printed one (stderr also carries its log lines);
    # else what it printed (calibrate and realign say why on stdout); else stderr's tail.
    err_lines = err.splitlines()
    error_lines = [line for line in err_lines if line.startswith(ERROR_PREFIX)]
    text = "\n".join(error_lines) or out or (err_lines[-1] if err_lines else "")
    return (text or f"the whiteboard command failed (exit {code})")[:MAX_ERROR_CHARS]
