"""Public API of whiteboard.mcp_server: the stdio MCP server behind `whiteboard mcp`.

It gives any Claude Code session the board_* tools (look at, draw on,
calibrate and fit the projector whiteboard). The server is named
"whiteboard", so Claude Code exposes them as `mcp__whiteboard__<tool>`.
It is a thin client of the daemon's HTTP API.
"""

from whiteboard.mcp_server.app import SERVER_NAME, build_server
from whiteboard.mcp_server.board_tools import BoardTools
from whiteboard.mcp_server.launch import run_stdio_server

__all__ = ["SERVER_NAME", "BoardTools", "build_server", "run_stdio_server"]
