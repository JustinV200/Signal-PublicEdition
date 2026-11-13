"""run_stdio_server: serves the sessions MCP tools on stdin/stdout, wired to the real daemon.

This is what `sessions mcp` runs. stdout is the MCP protocol channel, so
nothing here prints; logging goes to stderr.
"""

import logging
from functools import partial

from claude_sessions.config import Settings
from claude_sessions.ipc import call_running_daemon
from claude_sessions.mcp.app import build_server
from claude_sessions.mcp.tools import SessionTools

logger = logging.getLogger(__name__)


def run_stdio_server(settings: Settings) -> None:
    """Serve until the MCP client closes stdin.

    Args:
        settings: Repo roots for listings, and the daemon's address (started on first use).
    """
    tools = SessionTools(settings, partial(call_running_daemon, settings))
    server = build_server(tools)
    logger.info("sessions MCP server ready on stdio (daemon port %d)", settings.daemon_port)
    server.run("stdio")
