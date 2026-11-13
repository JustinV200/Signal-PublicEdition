"""Run the setup CLI (tools/setup) for the wizard and stream its output a line at a time.

The console never imports the setup tool (tools stay standalone): it runs
`uv run --project tools/setup --frozen --quiet setup <args>` in the repo root, with
stdout and stderr merged, so a long install shows live. One run at a time: two
wizard clicks must never write progress.json or install the same tool at once.
"""

import asyncio
import contextlib
import os
import shutil
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from signal_console.launch import clean_env
from signal_console.setup_cli.requests import SetupCall

_PIPE = asyncio.subprocess.PIPE
# Exit code when the setup command can't even start (uv missing), as a shell would give.
EXIT_NOT_FOUND = 127
# Unbuffered UTF-8 output, so lines arrive as they're printed and decode the same everywhere.
_CHILD_ENV = {"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}


def default_prefix(repo_root: Path) -> list[str]:
    """The command that runs the setup CLI, before its own arguments."""
    setup_project = str(repo_root / "tools" / "setup")
    return ["uv", "run", "--project", setup_project, "--frozen", "--quiet", "setup"]


class SetupBusy(RuntimeError):
    """Another setup command is still running (a 409)."""


class SetupRunner:
    """Runs one setup CLI command at a time and streams its lines."""

    def __init__(self, prefix: Sequence[str], cwd: Path) -> None:
        """
        Args:
            prefix: The program and arguments before the setup command (tests pass a fake CLI).
            cwd: Where it runs (the repo root).
        """
        self._prefix, self._cwd = list(prefix), cwd
        self._lock = asyncio.Lock()

    def check_free(self) -> None:
        """Raise SetupBusy when a command is running, before the page's stream starts."""
        if self._lock.locked():
            raise SetupBusy("another setup step is still running; wait for it to finish")

    async def run(self, call: SetupCall, on_line: Callable[[str], Awaitable[None]]) -> int:
        """Run `call`, passing each output line (without its newline) to `on_line`.

        `on_line` errors (the page went away) don't stop the command: it runs to the
        end so an install is never cut off halfway, and its result lands in progress.json.

        Returns:
            The command's exit code (EXIT_NOT_FOUND when the program is missing).

        Raises:
            SetupBusy: `call` is exclusive and another exclusive command is running.
        """
        if not call.exclusive:
            return await self._spawn(call, on_line)
        self.check_free()
        async with self._lock:
            return await self._spawn(call, on_line)

    async def _spawn(self, call: SetupCall, on_line: Callable[[str], Awaitable[None]]) -> int:
        """Start the command, feed its stdin, pass its lines on, return its exit code."""
        program = shutil.which(self._prefix[0])
        if program is None:
            await _quietly(on_line, f"{self._prefix[0]} isn't installed or isn't on PATH")
            return EXIT_NOT_FOUND
        process = await asyncio.create_subprocess_exec(
            program,
            *self._prefix[1:],
            *call.args,
            cwd=self._cwd,
            env={**clean_env(os.environ), **_CHILD_ENV},
            stdin=_PIPE if call.stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if call.stdin is not None and process.stdin is not None:
            process.stdin.write(call.stdin.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
        assert process.stdout is not None  # PIPE above
        async for raw in process.stdout:
            await _quietly(on_line, raw.decode("utf-8", "replace").rstrip("\r\n"))
        return await process.wait()


async def _quietly(on_line: Callable[[str], Awaitable[None]], line: str) -> None:
    """Pass a line on; a closed page connection only means nobody reads the rest."""
    # The page closed its stream: keep draining so the command finishes and saves progress.
    with contextlib.suppress(ConnectionError, RuntimeError):
        await on_line(line)
