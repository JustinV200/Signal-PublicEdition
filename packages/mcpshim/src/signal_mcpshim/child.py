"""One run of the real MCP server: spawn it, read and write its stdio lines, and stop it.

The child's stderr is inherited, so its logs land on the shim's stderr untouched.
"""

import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncIterator

log = logging.getLogger("mcpshim")

# MCP results can carry base64 screenshots, far past asyncio's 64 KiB default line limit.
MAX_LINE_BYTES = 64 * 1024 * 1024


class Child:
    """A spawned server process with pipes on stdin and stdout."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        """Wrap an already-started process; use `Child.spawn` to start one."""
        self._process = process

    @classmethod
    async def spawn(cls, command: list[str]) -> "Child":
        """Start `command` with piped stdin/stdout and inherited stderr.

        Raises:
            OSError: the command can't be started (e.g. not found).
        """
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            limit=MAX_LINE_BYTES,
        )
        return cls(process)

    @property
    def pid(self) -> int:
        """The process id, for logs."""
        return self._process.pid

    async def lines(self) -> AsyncIterator[bytes]:
        """Yield each non-empty stdout line without its line ending, until EOF.

        A line past MAX_LINE_BYTES ends the stream (logged), since the framing is lost.
        """
        assert self._process.stdout is not None
        while True:
            try:
                line = await self._process.stdout.readline()
            except ValueError:
                log.error("child %s wrote a line over %d bytes", self.pid, MAX_LINE_BYTES)
                return
            if not line:
                return
            stripped = line.rstrip(b"\r\n")
            if stripped:
                yield stripped

    async def write_line(self, data: bytes) -> None:
        """Write one line to the child's stdin.

        A child that already died is only logged: the shim notices the exit through its
        stdout and answers whatever was in flight.
        """
        assert self._process.stdin is not None
        try:
            self._process.stdin.write(data + b"\n")
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as error:
            log.info("child %s stdin closed (%s); message not delivered", self.pid, error)

    async def stop(self, grace: float) -> int:
        """Close stdin, wait up to `grace` seconds for an exit, then kill the process tree.

        Closing stdin is the main path: on Windows killing `uv run` can orphan the
        grandchild server, so the kill is only the fallback.

        Returns:
            The exit code.
        """
        assert self._process.stdin is not None
        with contextlib.suppress(OSError):
            self._process.stdin.close()
        try:
            return await asyncio.wait_for(self._process.wait(), grace)
        except TimeoutError:
            log.warning("child %s didn't exit within %.1fs; killing it", self.pid, grace)
        await self._kill_tree()
        return await self._process.wait()

    async def _kill_tree(self) -> None:
        """Kill the process and, on Windows, everything it started."""
        if sys.platform == "win32":
            await self._taskkill_tree()
        # Also covers non-Windows, and a taskkill that failed or couldn't start.
        with contextlib.suppress(ProcessLookupError):
            self._process.kill()

    async def _taskkill_tree(self) -> None:
        """Run `taskkill /T /F` on the child; a taskkill that can't start is only logged."""
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/T",
                "/F",
                "/PID",
                str(self.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        except OSError as error:
            log.warning("taskkill failed (%s); killing child %s alone", error, self.pid)
