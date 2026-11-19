"""build_server: the calendar MCPServer with every tool registered.

Tool behaviour lives in tools.py and model-facing text in descriptions.py;
this file only names the tools and wires them up, so tests can build the same
server around a fake-backed CalendarActions.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from calendar_tool import __version__
from calendar_tool.mcp_server import descriptions
from calendar_tool.mcp_server.tools import CalendarTools

# Claude Code names the tools mcp__calendar__<tool>; the .mcp.json key must match.
SERVER_NAME = "calendar"

_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
_ADDS = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)
_CHANGES = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)


@dataclass(frozen=True)
class _ToolSpec:
    """One tool to register: its MCP name, handler, description and hints."""

    name: str
    handler: Callable[..., Awaitable[str]]
    description: str
    annotations: ToolAnnotations


def build_server(tools: CalendarTools) -> MCPServer:
    """Create the calendar MCP server.

    Args:
        tools: Backs every tool.

    Returns:
        The server, ready for run("stdio") or an in-process mcp.Client.
    """
    server = MCPServer(
        SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=__version__
    )
    for spec in _tool_specs(tools):
        # Results are framed text, so no structured output schema.
        server.add_tool(
            spec.handler,
            name=spec.name,
            description=spec.description,
            annotations=spec.annotations,
            structured_output=False,
        )
    return server


def _tool_specs(tools: CalendarTools) -> tuple[_ToolSpec, ...]:
    """Every tool, in the order tools/list reports them."""
    return (
        _ToolSpec(
            "calendar_agenda", tools.calendar_agenda, descriptions.CALENDAR_AGENDA, _READ_ONLY
        ),
        _ToolSpec("calendar_create", tools.calendar_create, descriptions.CALENDAR_CREATE, _ADDS),
        _ToolSpec("calendar_update", tools.calendar_update, descriptions.CALENDAR_UPDATE, _CHANGES),
        _ToolSpec("calendar_delete", tools.calendar_delete, descriptions.CALENDAR_DELETE, _CHANGES),
        _ToolSpec(
            "calendar_respond", tools.calendar_respond, descriptions.CALENDAR_RESPOND, _CHANGES
        ),
    )
