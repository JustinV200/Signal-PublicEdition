"""McpHealer: between voice turns, reconnect the MCP servers the CLI reports as failed.

Claude Code doesn't reconnect stdio MCP servers on its own, and voice has no
/mcp to type, so SessionKeeper calls heal() before each request. Only `failed`
servers are retried. A server that is connected but stale (an old token, old
code) still reports as connected, so this can't see it: the servers re-read
their tokens themselves, and old code needs a hub restart.

The status probe and each reconnect are capped at CALL_TIMEOUT_S, so healing
can't stall a turn. A server whose reconnect fails or times out is left alone
for RETRY_AFTER_S, so one broken server doesn't add a slow reconnect to every turn.
"""

import asyncio
import logging
import math
import time
from collections.abc import Callable

from audiohub.brain.connection.protocol import BrainSession

logger = logging.getLogger(__name__)

FAILED_STATUS = "failed"
RETRY_AFTER_S = 300.0
# Longest wait for one control request; a stdio server normally reconnects in a few seconds.
CALL_TIMEOUT_S = 5.0


class McpHealer:
    """Remembers failed reconnects so each broken server is retried at most every RETRY_AFTER_S."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Prepare the healer.

        Args:
            clock: Monotonic seconds; tests pass a fake.
        """
        self._clock = clock
        self._last_failed_at: dict[str, float] = {}

    async def heal(self, session: BrainSession) -> None:
        """Reconnect each failed MCP server that isn't cooling down. Never raises.

        The SDK's control requests raise plain Exception, so every failure (a
        timeout included) is caught and logged: a status probe that fails must
        not cost the user their turn.

        Args:
            session: The open session.
        """
        try:
            statuses = await asyncio.wait_for(session.mcp_server_statuses(), CALL_TIMEOUT_S)
        except Exception as error:  # the SDK raises plain Exception (see the docstring)
            logger.warning("couldn't read MCP server status, not healing this turn: %r", error)
            return
        now = self._clock()
        for name, status in statuses.items():
            last_failed_at = self._last_failed_at.get(name, -math.inf)
            if status == FAILED_STATUS and now - last_failed_at >= RETRY_AFTER_S:
                await self._reconnect(session, name, now)

    async def _reconnect(self, session: BrainSession, name: str, now: float) -> None:
        """Reconnect one server, noting a failure or timeout for the cool-down."""
        logger.info("MCP server %s failed; reconnecting it", name)
        try:
            await asyncio.wait_for(session.reconnect_mcp_server(name), CALL_TIMEOUT_S)
        except Exception as error:  # the SDK raises plain Exception; TimeoutError too
            logger.warning("reconnecting MCP server %s failed: %r", name, error)
            self._last_failed_at[name] = now
            return
        self._last_failed_at.pop(name, None)
