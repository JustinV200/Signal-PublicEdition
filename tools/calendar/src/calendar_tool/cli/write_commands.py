"""The `calendar` write handlers: create, update, delete, respond.

Each builds the checked inputs, runs the CalendarActions call (which may open
the owner's Allow/Deny dialog) and prints one line. CalendarErrors propagate to
main(), which prints them as `calendar: error: ...`.
"""

import argparse

from calendar_tool.changes import EventEdit, EventRef, NewEvent
from calendar_tool.cli.commands import EXIT_OK, agenda_line
from calendar_tool.service import NOT_REFRESHED, WriteResult, build_actions


def create(args: argparse.Namespace) -> int:
    """`calendar create TITLE START [END] [--calendar] [--location] [--description]`."""
    new = NewEvent(args.title, args.start, args.end, args.calendar, args.location, args.description)
    _report("Created", build_actions().create(new))
    return EXIT_OK


def update(args: argparse.Namespace) -> int:
    """`calendar update EVENT_ID [--title] [--start] [--end] [--location] [--description]`."""
    edit = EventEdit(args.title, args.start, args.end, args.location, args.description)
    _report("Updated", build_actions().update(_ref(args), edit))
    return EXIT_OK


def delete(args: argparse.Namespace) -> int:
    """`calendar delete EVENT_ID [--calendar] [--series]`."""
    _report("Deleted", build_actions().delete(_ref(args)))
    return EXIT_OK


def respond(args: argparse.Namespace) -> int:
    """`calendar respond EVENT_ID accepted|declined|tentative [--calendar] [--series]`."""
    _report(f"Replied {args.response}", build_actions().respond(_ref(args), args.response))
    return EXIT_OK


def _ref(args: argparse.Namespace) -> EventRef:
    """The event the arguments name."""
    return EventRef(args.calendar, args.event_id, args.series)


def _report(done: str, result: WriteResult) -> None:
    """Print the outcome, and say so when the board's cache couldn't be refreshed."""
    print(f"{done}: {agenda_line(result.event)}" if result.event else f"{done}.")
    if not result.is_board_refreshed:
        print(NOT_REFRESHED)
