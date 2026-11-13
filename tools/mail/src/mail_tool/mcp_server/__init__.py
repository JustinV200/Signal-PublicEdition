"""Public API of mail_tool.mcp_server: the stdio MCP server named "mail"."""

from mail_tool.mcp_server.app import SERVER_NAME, build_server
from mail_tool.mcp_server.launch import run_stdio_server
from mail_tool.mcp_server.tools import MailTools

__all__ = ["SERVER_NAME", "MailTools", "build_server", "run_stdio_server"]
