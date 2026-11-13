"""build_server: the sessions MCPServer with every tool registered.

Tool behaviour lives in tools.py and model-facing text in descriptions.py;
this file only names the tools and wires them up, so tests can build the
same server around a fake daemon. (Named app.py to avoid confusion with the
MCP SDK's own `mcp.server` package.)
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from claude_sessions import __version__
from claude_sessions.mcp import descriptions
from claude_sessions.mcp.tools import SessionTools

# Claude Code names the tools mcp__sessions__<tool>; the .mcp.json key must match.
SERVER_NAME = "sessions"

_READ_ONLY = ToolAnnotations(read_only_hint=True)


@dataclass(frozen=True)
class _ToolSpec:
    """One tool to register: its MCP name, handler, description and hints."""

    name: str
    handler: Callable[..., Awaitable[str]]
    description: str
    annotations: ToolAnnotations | None = None


def build_server(tools: SessionTools) -> MCPServer:
    """Create the sessions MCP server.

    Args:
        tools: Backs every tool.

    Returns:
        The server, ready for run("stdio") or an in-process mcp.Client.
    """
    server = MCPServer(
        SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=__version__
    )
    for spec in _tool_specs(tools):
        # Results are JSON text, so no structured output schema.
        server.add_tool(
            spec.handler,
            name=spec.name,
            description=spec.description,
            annotations=spec.annotations,
            structured_output=False,
        )
    return server


def _tool_specs(tools: SessionTools) -> tuple[_ToolSpec, ...]:
    """Every tool, in the order tools/list reports them."""
    return (
        _ToolSpec("list_repos", tools.list_repos, descriptions.LIST_REPOS, _READ_ONLY),
        _ToolSpec("list_sessions", tools.list_sessions, descriptions.LIST_SESSIONS, _READ_ONLY),
        _ToolSpec("start_session", tools.start_session, descriptions.START_SESSION),
        _ToolSpec("send_to_session", tools.send_to_session, descriptions.SEND_TO_SESSION),
        _ToolSpec("session_status", tools.session_status, descriptions.SESSION_STATUS, _READ_ONLY),
        _ToolSpec("resume_session", tools.resume_session, descriptions.RESUME_SESSION),
        _ToolSpec("stop_session", tools.stop_session, descriptions.STOP_SESSION),
        _ToolSpec(
            "list_managed_sessions",
            tools.list_managed_sessions,
            descriptions.LIST_MANAGED_SESSIONS,
            _READ_ONLY,
        ),
    )
