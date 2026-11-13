"""`whiteboard mcp`: run the stdio MCP server exposing the board_* tools (for .mcp.json).

stdout carries the MCP protocol, so this command prints nothing; logs go to
stderr. It returns when the client closes stdin.
"""

import argparse

from whiteboard.cli.command import EXIT_OK, Command, no_arguments
from whiteboard.config import Settings


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Serve MCP over stdin/stdout until the client disconnects."""
    # Imported here: the MCP SDK is slow to import and other commands don't need it.
    from whiteboard.mcp_server import run_stdio_server

    run_stdio_server(settings, args.config)
    return EXIT_OK


COMMAND = Command(
    name="mcp",
    help="run as a stdio MCP server exposing the board_* tools (for .mcp.json)",
    add_arguments=no_arguments,
    run=run,
)
