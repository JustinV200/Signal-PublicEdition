"""run_stdio_server: serves the mail MCP tools on stdin/stdout, wired to the real accounts.

This is what `mail mcp` runs. stdout is the MCP protocol channel, so nothing
here prints; logging goes to stderr (set up by the CLI).
"""

import logging

from mail_tool.mcp_server.app import build_server
from mail_tool.mcp_server.tools import MailTools
from mail_tool.service import build_service

logger = logging.getLogger(__name__)


def run_stdio_server() -> None:
    """Serve until the MCP client closes stdin.

    Raises:
        SetupError: .state/mail.toml exists but is invalid.
    """
    server = build_server(MailTools(build_service()))
    logger.info("mail MCP server ready on stdio")
    server.run("stdio")
