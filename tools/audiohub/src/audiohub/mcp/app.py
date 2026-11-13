"""Builds the audiohub `MCPServer` and registers its tools on it.

Tool behaviour lives in notify_tool.py and music_tools.py; model-facing text
in descriptions.py. This file only names the tools and wires them up, so the
same server can be built with fakes in tests. (Named app.py, not server.py,
to avoid confusion with the SDK's own `mcp.server` package.)
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from audiohub import __version__
from audiohub.mcp import descriptions
from audiohub.mcp.music_tools import MusicTools
from audiohub.mcp.notify_tool import NotifyTool

# Claude Code names tools mcp__<server>__<tool>; the voice brain auto-allows
# the mcp__audiohub__ prefix, so this name and the .mcp.json key must match it.
SERVER_NAME = "audiohub"

_READ_ONLY = ToolAnnotations(read_only_hint=True)


@dataclass(frozen=True)
class _ToolSpec:
    """One tool to register: its MCP name, handler, and model-facing description."""

    name: str
    handler: Callable[..., Awaitable[str]]
    description: str
    annotations: ToolAnnotations | None = None


def build_server(notify_tool: NotifyTool, music_tools: MusicTools) -> MCPServer:
    """Create the audiohub MCP server with every tool registered.

    Args:
        notify_tool: Backs `notify` (sends messages to the voice hub).
        music_tools: Backs the `music_*` tools.

    Returns:
        The server, ready for `run("stdio")` or in-process `call_tool`.
    """
    server = MCPServer(
        SERVER_NAME, instructions=descriptions.SERVER_INSTRUCTIONS, version=__version__
    )
    for spec in _tool_specs(notify_tool, music_tools):
        # Every tool returns one plain sentence, so no structured output schema.
        server.add_tool(
            spec.handler,
            name=spec.name,
            description=spec.description,
            annotations=spec.annotations,
            structured_output=False,
        )
    return server


def _tool_specs(notify_tool: NotifyTool, music: MusicTools) -> tuple[_ToolSpec, ...]:
    """The full tool list, in the order `tools/list` reports it."""
    return (
        _ToolSpec("notify", notify_tool.notify, descriptions.NOTIFY),
        _ToolSpec(
            "music_now_playing", music.now_playing, descriptions.MUSIC_NOW_PLAYING, _READ_ONLY
        ),
        _ToolSpec("music_play", music.play, descriptions.MUSIC_PLAY),
        _ToolSpec("music_pause", music.pause, descriptions.MUSIC_PAUSE),
        _ToolSpec("music_next", music.next, descriptions.MUSIC_NEXT),
        _ToolSpec("music_previous", music.previous, descriptions.MUSIC_PREVIOUS),
        _ToolSpec("music_set_volume", music.set_volume, descriptions.MUSIC_SET_VOLUME),
        _ToolSpec(
            "music_search_and_play", music.search_and_play, descriptions.MUSIC_SEARCH_AND_PLAY
        ),
        _ToolSpec("music_play_liked", music.play_liked, descriptions.MUSIC_PLAY_LIKED),
        _ToolSpec("music_queue", music.queue, descriptions.MUSIC_QUEUE),
    )
