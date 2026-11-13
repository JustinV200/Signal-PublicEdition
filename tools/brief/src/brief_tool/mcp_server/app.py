"""build_server: the brief MCPServer with its tools registered.

Tool behaviour is in brief_tools.py and away_tools.py, model-facing text in
descriptions.py; this file only names the tools and wires them up. (Named app.py
so it isn't confused with the SDK's own `mcp.server` package.)
"""

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from brief_tool.mcp_server import descriptions
from brief_tool.mcp_server.away_tools import AwayTools
from brief_tool.mcp_server.brief_tools import BriefTools

# Claude Code names the tools mcp__brief__<tool>; the .mcp.json key must match, and the
# prompt hook finds brief_me results by that name (brief_tool.hooks.transcript).
SERVER_NAME = "brief"
VERSION = "0.1.0"

_READ_ONLY = ToolAnnotations(read_only_hint=True)
# Logs a delivery (so it can be acked later) but changes nothing the owner sees.
_RECORDS = ToolAnnotations(read_only_hint=False, destructive_hint=False)
_IDEMPOTENT = ToolAnnotations(idempotent_hint=True, destructive_hint=False)


def build_server(brief: BriefTools, away: AwayTools) -> MCPServer:
    """Create the brief MCP server.

    Args:
        brief: Backs the brief_* tools.
        away: Backs the away_* tools.

    Returns:
        The server, ready for run("stdio") or an in-process client.
    """
    server = MCPServer(SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=VERSION)
    specs = (
        ("brief_me", brief.brief_me, descriptions.BRIEF_ME, _RECORDS),
        ("brief_ack", brief.brief_ack, descriptions.BRIEF_ACK, _READ_ONLY),
        ("brief_log", brief.brief_log, descriptions.BRIEF_LOG, _RECORDS),
        ("brief_resolve", brief.brief_resolve, descriptions.BRIEF_RESOLVE, _IDEMPOTENT),
        ("brief_get", brief.brief_get, descriptions.BRIEF_GET, _READ_ONLY),
        ("brief_undo", brief.brief_undo, descriptions.BRIEF_UNDO, _READ_ONLY),
        ("away_on", away.away_on, descriptions.AWAY_ON, _IDEMPOTENT),
        ("away_off", away.away_off, descriptions.AWAY_OFF, _IDEMPOTENT),
        ("away_status", away.away_status, descriptions.AWAY_STATUS, _READ_ONLY),
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
