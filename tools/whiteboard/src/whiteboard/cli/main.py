"""`whiteboard` entry point: builds the argparse parser from the command registry and dispatches.

The command list lives in cli/commands/__init__.py. Errors a user can fix
(bad config, daemon won't start, daemon refused a request) print one clean
line instead of a traceback. Logs go to stderr, so `whiteboard mcp` keeps
stdout for the protocol.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from signal_tasks import StateFileError

from whiteboard.cli.command import EXIT_USER_ERROR, Command
from whiteboard.cli.commands import COMMANDS
from whiteboard.config import ConfigError, load_settings
from whiteboard.daemon_client import DaemonApiError, DaemonStartError

# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# StateFileError: `tasks show` found the console's task list but couldn't read it.
_USER_ERRORS = (ConfigError, DaemonApiError, DaemonStartError, StateFileError)


def build_parser(commands: Sequence[Command] = COMMANDS) -> argparse.ArgumentParser:
    """Build the `whiteboard` parser with one subparser per command.

    Returns:
        The parser. Parsed args carry the command name in `args.command`.
    """
    parser = argparse.ArgumentParser(
        prog="whiteboard",
        description="Projector + webcam whiteboard: Claude sees the board and draws on it.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        default=None,
        help="config file (default: tools/whiteboard/whiteboard.toml if it exists)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in commands:
        subparser = subparsers.add_parser(command.name, help=command.help, description=command.help)
        # SUPPRESS keeps a --config given before the command name from being reset.
        subparser.add_argument(
            "--config", type=Path, metavar="PATH", default=argparse.SUPPRESS, help="config file"
        )
        command.add_arguments(subparser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, load settings, and run the chosen command.

    Args:
        argv: Arguments without the program name (default: sys.argv[1:]).

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    command = next(command for command in COMMANDS if command.name == args.command)
    try:
        return command.run(args, load_settings(args.config))
    except _USER_ERRORS as error:
        print(f"whiteboard: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
