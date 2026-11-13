"""Runs the whiteboard MCP server over stdio, connected to the real daemon.

This is what `whiteboard mcp` calls. stdout is the MCP protocol channel, so
nothing here prints: logs go to stderr. The daemon is found or started on
the first tool call, not here, so listing tools never lights the projector.
"""

import logging
from pathlib import Path

from whiteboard.config import STATE_DIR, Settings
from whiteboard.daemon_client import DaemonConnection, DaemonLocation
from whiteboard.mcp_server.app import build_server
from whiteboard.mcp_server.board_tools import BoardTools

logger = logging.getLogger(__name__)


def run_stdio_server(settings: Settings, config_path: Path | None) -> None:
    """Serve the board_* tools on stdin/stdout until the client disconnects.

    Args:
        settings: Supplies the daemon port.
        config_path: Passed to a daemon this server starts, so both use one config.
    """
    location = DaemonLocation(STATE_DIR, settings.display.port, config_path)
    server = build_server(BoardTools(DaemonConnection(location)))
    logger.info("whiteboard MCP server ready on stdio (daemon port %s)", settings.display.port)
    server.run("stdio")
