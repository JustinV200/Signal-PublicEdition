"""Public API of brief_tool.mcp_server: the stdio MCP server named "brief"."""

from brief_tool.mcp_server.app import SERVER_NAME, build_server
from brief_tool.mcp_server.away_tools import AwayTools
from brief_tool.mcp_server.brief_tools import BriefTools

__all__ = ["SERVER_NAME", "AwayTools", "BriefTools", "build_server"]
