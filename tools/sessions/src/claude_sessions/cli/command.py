"""add_command: registers one `sessions <name>` subcommand and the handler main() runs for it.

Every handler has the shape handler(args, settings) -> exit code. Commands log
at WARNING; the long-running serve and mcp raise that with use_info_logging.
"""

import argparse
import logging
from collections.abc import Callable

from claude_sessions.config import Settings

Handler = Callable[[argparse.Namespace, Settings], int]
QUIET_LOG_LEVEL = logging.WARNING


def add_command(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    handler: Handler,
) -> argparse.ArgumentParser:
    """Add a subcommand.

    Args:
        subparsers: From ArgumentParser.add_subparsers().
        name: The word after `sessions`.
        help_text: One line for --help.
        handler: Runs the command.

    Returns:
        The subcommand's parser, for adding its own arguments.
    """
    parser = subparsers.add_parser(name, help=help_text, description=help_text)
    parser.set_defaults(handler=handler, log_level=QUIET_LOG_LEVEL)
    return parser


def use_info_logging(parser: argparse.ArgumentParser) -> None:
    """Make a command log at INFO, for long-running commands whose log is their only output.

    Args:
        parser: The command's parser from add_command.
    """
    parser.set_defaults(log_level=logging.INFO)
