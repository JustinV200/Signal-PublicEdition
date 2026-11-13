"""build_server: the sleepmode MCPServer with its three tools registered.

Tool behaviour is in tools.py and model-facing text in descriptions.py; this file
only names the tools and wires them up. (Named app.py so it isn't confused with the
SDK's own `mcp.server` package.)
"""

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from sleepmode import __version__
from sleepmode.mcp_server import descriptions
from sleepmode.mcp_server.tools import SleepTools

# Claude Code names the tools mcp__sleepmode__<tool>; the .mcp.json key must match.
SERVER_NAME = "sleepmode"

_READ_ONLY = ToolAnnotations(read_only_hint=True)
# Turning sleep mode on twice, or off twice, ends in the same place.
_IDEMPOTENT = ToolAnnotations(idempotent_hint=True, destructive_hint=False)


def build_server(tools: SleepTools) -> MCPServer:
    """Create the sleepmode MCP server.

    Args:
        tools: Backs every tool.

    Returns:
        The server, ready for run("stdio") or an in-process client.
    """
    server = MCPServer(
        SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=__version__
    )
    specs = (
        ("sleep_mode_on", tools.sleep_mode_on, descriptions.SLEEP_MODE_ON, _IDEMPOTENT),
        ("sleep_mode_off", tools.sleep_mode_off, descriptions.SLEEP_MODE_OFF, _IDEMPOTENT),
        ("sleep_mode_status", tools.sleep_mode_status, descriptions.SLEEP_MODE_STATUS, _READ_ONLY),
    )
    for name, handler, description, annotations in specs:
        # Every tool answers in plain text, so no structured output schema.
        server.add_tool(
            handler,
            name=name,
            description=description,
            annotations=annotations,
            structured_output=False,
        )
    return server
