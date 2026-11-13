"""Runs the audiohub MCP server over stdio, wired to the real kernel client and music backend.

This is what `audiohub mcp` calls. stdout is the MCP protocol channel, so
nothing here prints: logging goes to stderr (the CLI configures it, and the
SDK's own handler writes to stderr too).
"""

import logging

from audiohub.config import Settings
from audiohub.mcp.app import build_server
from audiohub.mcp.music_tools import MusicTools
from audiohub.mcp.notify_tool import NotifyTool
from audiohub.music import create_controller

logger = logging.getLogger(__name__)


def run_stdio_server(settings: Settings) -> None:
    """Serve the audiohub tools on stdin/stdout until the client disconnects.

    Args:
        settings: Supplies the hub address (`ipc`) for `notify` and the
            backend choice (`music`) for the `music_*` tools.
    """
    # create_controller makes no network or Windows calls, so building it up
    # front costs nothing; Spotify login problems surface per call instead.
    music_tools = MusicTools(create_controller(settings.music))
    server = build_server(NotifyTool(settings.ipc), music_tools)
    ipc = settings.ipc
    logger.info("audiohub MCP server ready on stdio (hub at %s:%s)", ipc.host, ipc.port)
    server.run("stdio")
