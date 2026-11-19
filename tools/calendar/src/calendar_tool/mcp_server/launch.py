"""run_stdio_server: serves the calendar MCP tools on stdin/stdout, wired to the real sign-in.

This is what `calendar mcp` runs. stdout is the MCP protocol channel, so nothing
here prints. It starts without a sign-in; each tool call opens it.
"""

from calendar_tool.mcp_server.app import build_server
from calendar_tool.mcp_server.tools import CalendarTools
from calendar_tool.service import build_actions


def run_stdio_server() -> None:
    """Serve until the MCP client closes stdin."""
    build_server(CalendarTools(build_actions())).run("stdio")
