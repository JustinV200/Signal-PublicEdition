"""Command line entry point: `mcpshim -- <real server command...>`.

Claude Code's .mcp.json runs this in place of each stdio server, one shim per server,
so tool names stay the same. Logs go to stderr; stdout is the protocol.
"""

import asyncio
import logging
import sys

from signal_mcpshim.shim import Shim
from signal_mcpshim.stdio import start_stdin_reader, write_stdout_line

USAGE = "usage: mcpshim -- <server command> [args...]"


def main(argv: list[str] | None = None) -> int:
    """Run the shim around the command in `argv` (default: sys.argv[1:]).

    Returns:
        0 after the client hangs up, 2 when no command was given.
    """
    command = list(sys.argv[1:] if argv is None else argv)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        print(USAGE, file=sys.stderr)
        return 2
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="mcpshim: %(message)s")
    asyncio.run(_run(command))
    return 0


async def _run(command: list[str]) -> None:
    """Wire the shim to this process's stdin and stdout and relay until stdin closes."""
    shim = Shim(command, write_stdout_line)
    loop = asyncio.get_running_loop()
    start_stdin_reader(lambda line: loop.call_soon_threadsafe(shim.feed_client_line, line))
    await shim.run()
