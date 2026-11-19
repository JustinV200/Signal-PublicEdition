"""`calendar` entry point: builds the argparse parser and runs the chosen command.

Errors the owner can act on (setup, re-auth, offline, API errors) print one
clean line to stderr and exit 2, so the scheduled task's failure is visible in
Task Scheduler's last-run result.
"""

import argparse
import sys
from collections.abc import Sequence

from calendar_tool.agenda import DEFAULT_DAYS, MAX_DAYS
from calendar_tool.cli import commands
from calendar_tool.cli.write_parser import add_write_commands
from calendar_tool.errors import CalendarError
from calendar_tool.paths import OWNER_EMAIL

EXIT_USER_ERROR = 2
# Conventional exit code for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130


def _days(text: str) -> int:
    """argparse type for --days: an integer from 1 to MAX_DAYS."""
    value = int(text)
    if not 1 <= value <= MAX_DAYS:
        raise argparse.ArgumentTypeError(f"--days must be 1-{MAX_DAYS}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """The `calendar` parser with every subcommand; parsed args carry `handler`."""
    parser = argparse.ArgumentParser(
        prog="calendar", description="Google Calendar for the idle board and for Claude."
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    sub.add_parser("setup", help="print the setup steps and check the client file")
    add = sub.add_parser("add", help="sign in through the browser")
    add.add_argument("--email", default=OWNER_EMAIL, help=f"expected address ({OWNER_EMAIL})")
    agenda = sub.add_parser("agenda", help="print the upcoming events and their ids")
    agenda.add_argument("--days", type=_days, default=DEFAULT_DAYS, help=f"1-{MAX_DAYS}")
    agenda.add_argument("--json", action="store_true", help="print JSON, with ids and flags")
    sub.add_parser("sync-cache", help="rewrite .state/agenda.json for the idle board")
    sub.add_parser("mcp", help="run the stdio MCP server")

    handlers = {
        "setup": commands.run_setup,
        "add": commands.add,
        "agenda": commands.agenda,
        "sync-cache": commands.sync,
        "mcp": commands.serve_mcp,
    }
    for name, handler in handlers.items():
        sub.choices[name].set_defaults(handler=handler)
    add_write_commands(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the command.

    Args:
        argv: Arguments without the program name (default sys.argv[1:]).

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    # Event titles can hold characters a legacy console code page can't print.
    if sys.stdout is not None:  # None under pythonw (the scheduled task)
        sys.stdout.reconfigure(errors="replace")
    try:
        return args.handler(args)
    except CalendarError as error:
        print(f"calendar: error: {error}", file=sys.stderr)  # print() skips a None stream
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
