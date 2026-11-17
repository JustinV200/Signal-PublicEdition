"""The five chamber tool handlers: thin wrappers over the daemon client.

Each call runs the blocking client in a worker thread. A DaemonError becomes a ToolError
carrying the client's message (which already says how to start the daemon).
"""

import asyncio
import importlib
import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError


class ChamberTools:
    """Handlers for chamber_start, chamber_approve, chamber_status, chamber_list, chamber_ask."""

    def __init__(self, state_dir: Path) -> None:
        """Args: state_dir: where the daemon writes daemon.json (config.state_dir)."""
        self._state_dir = state_dir

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> str:
        """Call a DaemonClient method off the event loop; return its dict as JSON text."""
        # Looked up per call (not imported at the top) so tests can swap the module and the server
        # starts without loading the daemon's heavy imports.
        daemon = importlib.import_module("analysis_chamber.daemon")
        try:
            client = daemon.DaemonClient(self._state_dir)
            result = await asyncio.to_thread(getattr(client, method), *args, **kwargs)
        except daemon.DaemonError as error:
            raise ToolError(str(error)) from error
        return json.dumps(result, indent=2)

    async def chamber_start(self, question: str) -> str:
        """Draft a plan for the question. Returns JSON {run_id, plan}."""
        return await self._call("start", question)

    async def chamber_approve(self, run: str, edits: str = "", personal: bool | None = None) -> str:
        """Approve the plan or revise it with edits. personal comes from the user only."""
        return await self._call("approve", run, edits=edits or None, personal=personal)

    async def chamber_status(self, run: str) -> str:
        """Return the run's status JSON (includes `publish` only when publishing is allowed)."""
        return await self._call("status", run)

    async def chamber_list(self) -> str:
        """Return every run's summary as JSON."""
        return await self._call("list")

    async def chamber_ask(self, run: str, question: str) -> str:
        """Ask a question about a run; returns JSON {answer}."""
        return await self._call("ask", run, question)
