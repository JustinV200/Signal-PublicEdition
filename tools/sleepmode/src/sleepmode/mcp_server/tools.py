"""SleepTools: the behaviour behind each sleepmode MCP tool.

Each call runs the blocking SleepMode method in a worker thread (DDC/CI, HTTP to
the whiteboard and schtasks all block), and answers with the same plain text as
the CLI. Expected failures become ToolError, so the model gets a readable error.
Sleep and wake take one lock, so two calls at once (a voice "good morning" racing an
agent's sleep_mode_on) run one after the other instead of interleaving.
"""

import asyncio
import threading
from collections.abc import Callable

from mcp.server.mcpserver.exceptions import ToolError

from sleepmode.control import (
    SleepMode,
    SleepModeError,
    describe_sleep,
    describe_status,
    describe_wake,
)


class SleepTools:
    """Backs every sleepmode MCP tool. Parameters are named as the tools' schemas show them."""

    def __init__(self, sleep_mode: SleepMode) -> None:
        """Configure the tools.

        Args:
            sleep_mode: The state machine (real from sleepmode.wiring, or with fakes in tests).
        """
        self._sleep_mode = sleep_mode
        # A thread lock, held inside the worker thread: an interleaved wake could save
        # "awake" over a new sleep, leaving its screens dark with no keeper.
        self._lock = threading.Lock()

    async def sleep_mode_on(self, wake_at: str = "") -> str:
        """See descriptions.SLEEP_MODE_ON."""
        try:
            state = await asyncio.to_thread(
                self._locked, self._sleep_mode.sleep, wake_at.strip() or None
            )
        except (ValueError, SleepModeError) as error:
            raise ToolError(str(error)) from error
        return describe_sleep(state)

    async def sleep_mode_off(self) -> str:
        """See descriptions.SLEEP_MODE_OFF."""
        return describe_wake(
            await asyncio.to_thread(self._locked, self._sleep_mode.wake, "request")
        )

    async def sleep_mode_status(self) -> str:
        """See descriptions.SLEEP_MODE_STATUS."""
        try:
            return describe_status(await asyncio.to_thread(self._sleep_mode.status))
        except SleepModeError as error:
            raise ToolError(str(error)) from error

    def _locked[T](self, method: Callable[..., T], *args: object) -> T:
        """Run a SleepMode method holding the lock (in the worker thread)."""
        with self._lock:
            return method(*args)
