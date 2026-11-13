"""Builds the whiteboard `MCPServer` and registers the board_* tools on it.

Tool behaviour lives in board_tools.py and model-facing text in
descriptions.py; this file only names the tools and wires them up, so the
server can be built against a fake daemon in tests.
"""

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from whiteboard import __version__
from whiteboard.mcp_server import descriptions
from whiteboard.mcp_server.board_tools import BoardTools

# Claude Code names tools mcp__<server>__<tool>; the board agent auto-allows the
# mcp__whiteboard__ prefix, so this name and the .mcp.json key must match it.
SERVER_NAME = "whiteboard"

_READ_ONLY = ToolAnnotations(read_only_hint=True)

# (tool name, handler, description, annotations or None)
ToolSpec = tuple[str, Callable[..., Any], str, ToolAnnotations | None]


def build_server(tools: BoardTools) -> MCPServer:
    """Create the whiteboard MCP server with every tool registered.

    Args:
        tools: The tool handlers, bound to a daemon connection.

    Returns:
        The server, ready for `run("stdio")` or an in-process client.
    """
    server = MCPServer(
        SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=__version__
    )
    for name, handler, description, annotations in _tool_specs(tools):
        # Results are text (or an image plus text), so no structured output schema.
        server.add_tool(
            handler,
            name=name,
            description=description,
            annotations=annotations,
            structured_output=False,
        )
    return server


def _tool_specs(tools: BoardTools) -> tuple[ToolSpec, ...]:
    """Every tool: its name, handler, description and annotations."""
    return (
        ("board_look", tools.look, descriptions.BOARD_LOOK, None),
        ("board_draw", tools.draw, descriptions.BOARD_DRAW, None),
        ("board_move", tools.move, descriptions.BOARD_MOVE, None),
        ("board_remove", tools.remove, descriptions.BOARD_REMOVE, None),
        ("board_clear", tools.clear, descriptions.BOARD_CLEAR, None),
        ("board_placeholder", tools.placeholder, descriptions.BOARD_PLACEHOLDER, None),
        ("board_list", tools.list_items, descriptions.BOARD_LIST, _READ_ONLY),
        ("board_highlight", tools.highlight, descriptions.BOARD_HIGHLIGHT, None),
        ("board_calibrate", tools.calibrate, descriptions.BOARD_CALIBRATE, None),
        ("board_fit", tools.fit, descriptions.BOARD_FIT, None),
        ("board_realign", tools.realign, descriptions.BOARD_REALIGN, None),
        ("board_save", tools.save, descriptions.BOARD_SAVE, None),
        ("board_load", tools.load, descriptions.BOARD_LOAD, None),
        ("board_saves", tools.list_saves, descriptions.BOARD_SAVES, _READ_ONLY),
        ("board_delete_save", tools.delete_save, descriptions.BOARD_DELETE_SAVE, None),
        ("board_todo_show", tools.todo_show, descriptions.BOARD_TODO_SHOW, None),
        ("board_todo_hide", tools.todo_hide, descriptions.BOARD_TODO_HIDE, None),
        ("board_todo_sync", tools.todo_sync, descriptions.BOARD_TODO_SYNC, None),
        ("board_todo_done", tools.todo_done, descriptions.BOARD_TODO_DONE, None),
        ("board_todo_undone", tools.todo_undone, descriptions.BOARD_TODO_UNDONE, None),
        ("board_tasks_show", tools.tasks_show, descriptions.BOARD_TASKS_SHOW, None),
        ("board_idle_show", tools.idle_show, descriptions.BOARD_IDLE_SHOW, None),
        ("board_idle_hide", tools.idle_hide, descriptions.BOARD_IDLE_HIDE, None),
        ("board_night_show", tools.night_show, descriptions.BOARD_NIGHT_SHOW, None),
        ("board_night_hide", tools.night_hide, descriptions.BOARD_NIGHT_HIDE, None),
    )
