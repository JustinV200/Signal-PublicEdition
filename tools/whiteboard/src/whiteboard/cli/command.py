"""The `Command` record every `whiteboard <name>` subcommand exports, plus a daemon helper.

To add a command: define `Command(...)` in a module under cli/commands/ and
append it to `COMMANDS` in cli/commands/__init__.py. main.py builds the
argparse subparser from it.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from whiteboard.config import STATE_DIR, Settings
from whiteboard.daemon_client import DaemonConnection, DaemonLocation

EXIT_OK = 0
EXIT_FAILED = 1
# Something the user can fix: bad arguments or config, or the daemon refused a request.
EXIT_USER_ERROR = 2


@dataclass(frozen=True)
class Command:
    """One subcommand.

    Attributes:
        name: The word typed after `whiteboard`, e.g. "look".
        help: One-line description for `whiteboard --help`.
        add_arguments: Adds the command's own options (the global --config is added for it).
        run: Executes the command with the parsed args and loaded settings; returns the exit code.
    """

    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace, Settings], int]


def no_arguments(parser: argparse.ArgumentParser) -> None:
    """add_arguments for commands with no options of their own."""


def daemon_connection(
    args: argparse.Namespace, settings: Settings, is_auto_start: bool = True
) -> DaemonConnection:
    """Connect to the daemon, starting it detached (with the same --config) if needed.

    Args:
        args: Parsed args (for --config).
        settings: Loaded settings (for the port).
        is_auto_start: False to fail with DaemonStartError instead of starting one.
    """
    location = DaemonLocation(STATE_DIR, settings.display.port, args.config)
    return DaemonConnection(location, is_auto_start)
