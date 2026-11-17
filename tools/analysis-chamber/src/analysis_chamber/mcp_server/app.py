"""build_server and run_stdio_server: the "analysis-chamber" MCP server for `analysis-chamber mcp`.

stdout is the protocol channel, so nothing here prints.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from analysis_chamber.mcp_server import descriptions
from analysis_chamber.mcp_server.tools import ChamberTools

# Claude Code names the tools mcp__analysis-chamber__<tool>; the .mcp.json key must match.
SERVER_NAME = "analysis-chamber"


def build_server(state_dir: Path) -> MCPServer:
    """Create the server with exactly the five chamber tools.

    Args:
        state_dir: The daemon's state folder (config.state_dir).

    Returns:
        The server, ready for run("stdio") or an in-process mcp.Client.
    """
    tools = ChamberTools(state_dir)
    server = MCPServer(SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS)
    specs = (
        ("chamber_start", tools.chamber_start, descriptions.CHAMBER_START),
        ("chamber_approve", tools.chamber_approve, descriptions.CHAMBER_APPROVE),
        ("chamber_status", tools.chamber_status, descriptions.CHAMBER_STATUS),
        ("chamber_list", tools.chamber_list, descriptions.CHAMBER_LIST),
        ("chamber_ask", tools.chamber_ask, descriptions.CHAMBER_ASK),
    )
    for name, handler, description in specs:
        # Results are JSON text, so no structured output schema.
        server.add_tool(handler, name=name, description=description, structured_output=False)
    return server


def run_stdio_server(state_dir: Path) -> None:
    """Serve until the MCP client closes stdin."""
    build_server(state_dir).run("stdio")
