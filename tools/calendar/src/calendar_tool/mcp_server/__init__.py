"""Public API of calendar_tool.mcp_server: the stdio MCP server named "calendar"."""

from calendar_tool.mcp_server.app import SERVER_NAME, build_server
from calendar_tool.mcp_server.launch import run_stdio_server
from calendar_tool.mcp_server.tools import TAG, CalendarTools

__all__ = ["SERVER_NAME", "TAG", "CalendarTools", "build_server", "run_stdio_server"]
