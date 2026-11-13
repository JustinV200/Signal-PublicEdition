"""build_server: the mail MCPServer with every tool registered.

Tool behaviour lives in tools.py and model-facing text in descriptions.py;
this file only names the tools and wires them up, so tests can build the same
server around a fake-backed service.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from mail_tool import __version__
from mail_tool.mcp_server import descriptions
from mail_tool.mcp_server.tools import MailTools

# Claude Code names the tools mcp__mail__<tool>; the .mcp.json key must match.
SERVER_NAME = "mail"

_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
_WRITES_DRAFT = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)
_SENDS = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)


@dataclass(frozen=True)
class _ToolSpec:
    """One tool to register: its MCP name, handler, description and hints."""

    name: str
    handler: Callable[..., Awaitable[str]]
    description: str
    annotations: ToolAnnotations


def build_server(tools: MailTools) -> MCPServer:
    """Create the mail MCP server.

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


def _tool_specs(tools: MailTools) -> tuple[_ToolSpec, ...]:
    """Every tool, in the order tools/list reports them."""
    return (
        _ToolSpec("mail_accounts", tools.mail_accounts, descriptions.MAIL_ACCOUNTS, _READ_ONLY),
        _ToolSpec("mail_search", tools.mail_search, descriptions.MAIL_SEARCH, _READ_ONLY),
        _ToolSpec("mail_read", tools.mail_read, descriptions.MAIL_READ, _READ_ONLY),
        _ToolSpec("mail_thread", tools.mail_thread, descriptions.MAIL_THREAD, _READ_ONLY),
        _ToolSpec("mail_draft", tools.mail_draft, descriptions.MAIL_DRAFT, _WRITES_DRAFT),
        _ToolSpec("mail_send_draft", tools.mail_send_draft, descriptions.MAIL_SEND_DRAFT, _SENDS),
    )
