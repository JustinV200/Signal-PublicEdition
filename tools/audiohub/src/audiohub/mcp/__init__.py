"""Public API of audiohub.mcp: the stdio MCP server behind `audiohub mcp`.

It gives any Claude Code session `notify` (speak to the user through the
voice hub's kernel) and the `music_*` controls. The server is named
"audiohub", so Claude Code exposes the tools as `mcp__audiohub__<tool>`.

Within this package `mcp` always means the official SDK: every import is
absolute, and this package is only ever imported as `audiohub.mcp`.
"""

from audiohub.mcp.app import SERVER_NAME, build_server
from audiohub.mcp.launch import run_stdio_server
from audiohub.mcp.music_tools import MusicTools, format_now_playing
from audiohub.mcp.notify_tool import NotifyTool

__all__ = [
    "SERVER_NAME",
    "MusicTools",
    "NotifyTool",
    "build_server",
    "format_now_playing",
    "run_stdio_server",
]
