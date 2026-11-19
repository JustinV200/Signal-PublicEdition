"""The `calendar` write subcommands' arguments: create, update, delete, respond.

Kept apart from main.py so the parser builder stays short. Each subcommand
carries its handler from write_commands.py.
"""

import argparse

from calendar_tool.changes import RESPONSES
from calendar_tool.cli import write_commands

PRIMARY = "primary"
CALENDAR_HELP = "calendar id from `agenda` (default primary)"
SERIES_HELP = "act on the whole repeating series, not just this occurrence"
TIME_HELP = "YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM local time"
ASKS = "asks you first unless the tool made it"


def add_write_commands(sub: argparse._SubParsersAction) -> None:
    """Add create, update, delete and respond to the `calendar` subparsers."""
    create = sub.add_parser("create", help="add an event (no guests, nobody notified)")
    create.add_argument("title")
    create.add_argument("start", help=TIME_HELP)
    create.add_argument("end", nargs="?", default="", help="optional for all-day (one day)")
    create.add_argument("--calendar", default=PRIMARY, help=CALENDAR_HELP)
    create.add_argument("--location", default="")
    create.add_argument("--description", default="")
    create.set_defaults(handler=write_commands.create)

    update = _event_parser(
        sub, "update", f"change an event's title, time, location or description; {ASKS}"
    )
    update.add_argument("--title")
    update.add_argument("--start", help=f"{TIME_HELP}; alone it keeps the length")
    update.add_argument("--end", help=TIME_HELP)
    update.add_argument("--location", help='"" removes it')
    update.add_argument("--description", help='"" removes it')
    update.set_defaults(handler=write_commands.update)

    delete = _event_parser(sub, "delete", f"delete an event; {ASKS}")
    delete.set_defaults(handler=write_commands.delete)

    respond = _event_parser(
        sub, "respond", "answer an invitation (asks you; Google emails the organizer)"
    )
    respond.add_argument("response", choices=RESPONSES)
    respond.set_defaults(handler=write_commands.respond)


def _event_parser(sub: argparse._SubParsersAction, name: str, text: str) -> argparse.ArgumentParser:
    """A subcommand that names one event: EVENT_ID, --calendar and --series."""
    parser = sub.add_parser(name, help=text)
    parser.add_argument("event_id", help="id from `agenda`")
    parser.add_argument("--calendar", default=PRIMARY, help=CALENDAR_HELP)
    parser.add_argument("--series", action="store_true", help=SERIES_HELP)
    return parser
