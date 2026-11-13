"""`audiohub` entry point: builds the argparse parser from the command registry and dispatches.

The command list lives in cli/commands/__init__.py; see cli/command.py for how
to add one. Errors a user can fix (bad config, unknown device, device won't
open) print one clean line instead of a traceback.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from audiohub.cli.command import Command
from audiohub.cli.commands import COMMANDS
from audiohub.cli.options import add_global_options, settings_from_args
from audiohub.config import ConfigError

EXIT_USER_ERROR = 2
# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def build_parser(commands: Sequence[Command] = COMMANDS) -> argparse.ArgumentParser:
    """Build the `audiohub` parser with one subparser per command.

    Args:
        commands: The registered commands (the default registry unless testing).

    Returns:
        The parser. Parsed args carry the command name in `args.command`.
    """
    parser = argparse.ArgumentParser(
        prog="audiohub",
        description="Voice chat, message kernel, music control and ducking for Claude.",
    )
    add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in commands:
        subparser = subparsers.add_parser(command.name, help=command.help, description=command.help)
        add_global_options(subparser, is_subcommand=True)
        command.add_arguments(subparser)
    return parser


def main(argv: Sequence[str] | None = None, commands: Sequence[Command] = COMMANDS) -> int:
    """Parse arguments, load settings, and run the chosen command.

    Args:
        argv: Arguments without the program name (default: sys.argv[1:]).
        commands: The registered commands (the default registry unless testing).

    Returns:
        The process exit code.
    """
    args = build_parser(commands).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    command = next(command for command in commands if command.name == args.command)
    try:
        return command.run(args, settings_from_args(args))
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except Exception as error:
        if not isinstance(error, _user_error_types()):
            raise
        print(f"audiohub: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR


def _user_error_types() -> tuple[type[Exception], ...]:
    """Errors caused by config or environment that the user can fix."""
    # Imported only once an error needs checking: audiohub.audio loads
    # sounddevice and numpy (~0.4 s), which most commands never use.
    from audiohub.audio import AudioStreamError, DeviceNotFoundError

    return (ConfigError, DeviceNotFoundError, AudioStreamError)
