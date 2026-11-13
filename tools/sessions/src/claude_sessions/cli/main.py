"""`sessions` entry point: builds the argparse parser and runs the chosen command.

Errors the user can act on (bad settings, unknown repo, refused request,
daemon not reachable) print one clean line instead of a traceback.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from claude_sessions.approvals import PermissionModeError
from claude_sessions.cli.daemon_commands import add_daemon_commands
from claude_sessions.cli.local_commands import add_local_commands
from claude_sessions.config import SettingsError, load_settings
from claude_sessions.ipc import (
    DaemonNotRunningError,
    DaemonRequestError,
    DaemonStartError,
    ProtocolError,
)
from claude_sessions.repos import RepoNotFoundError

EXIT_USER_ERROR = 2
# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_USER_ERRORS = (
    SettingsError,
    RepoNotFoundError,
    PermissionModeError,
    ProtocolError,
    DaemonRequestError,
    DaemonNotRunningError,
    DaemonStartError,
    TimeoutError,
    OSError,
)


def build_parser() -> argparse.ArgumentParser:
    """The `sessions` parser with every subcommand.

    Returns:
        The parser. Parsed args carry `handler` and `log_level`.
    """
    parser = argparse.ArgumentParser(
        prog="sessions",
        description="Start, resume and drive headless Claude Code sessions in local repos.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    add_local_commands(subparsers)
    add_daemon_commands(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, load settings and run the command.

    Args:
        argv: Arguments without the program name (default sys.argv[1:]).

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level, format=LOG_FORMAT, stream=sys.stderr)
    try:
        return args.handler(args, load_settings())
    except _USER_ERRORS as error:
        print(f"sessions: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
