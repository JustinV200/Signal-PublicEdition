"""`audiohub mcp`: run audiohub as a stdio MCP server (notify + music tools).

Started by Claude Code from the repo's `.mcp.json`. stdout carries the MCP
protocol, so this command prints nothing; logs go to stderr. It returns when
the client closes stdin.
"""

import argparse

from audiohub.cli.command import Command
from audiohub.config import Settings

EXIT_OK = 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """`mcp` has no options of its own beyond the global ones."""


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Serve MCP over stdin/stdout until the client disconnects.

    Returns:
        0 once the client has closed the connection.
    """
    # Imported here, not at module level: the MCP SDK adds ~0.6 s of imports,
    # and every other `audiohub` command loads this module via the registry.
    from audiohub.mcp import run_stdio_server

    run_stdio_server(settings)
    return EXIT_OK


COMMAND = Command(
    name="mcp",
    help="run as a stdio MCP server exposing notify and music tools (for .mcp.json)",
    add_arguments=add_arguments,
    run=run,
)
