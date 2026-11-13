"""run_stdio_server: serves the sleepmode MCP tools on stdin/stdout. `sleepmode mcp` runs this.

stdout is the MCP protocol channel, so nothing here prints; logs go to stderr and
.state/sleepmode.log.
"""

import logging

from sleepmode.control import SleepMode
from sleepmode.mcp_server.app import build_server
from sleepmode.mcp_server.tools import SleepTools

log = logging.getLogger(__name__)


def run_stdio_server(sleep_mode: SleepMode) -> None:
    """Serve until the MCP client closes stdin.

    Args:
        sleep_mode: The real state machine (sleepmode.wiring.build_sleep_mode()).
    """
    server = build_server(SleepTools(sleep_mode))
    log.info("sleepmode MCP server ready on stdio")
    server.run("stdio")
