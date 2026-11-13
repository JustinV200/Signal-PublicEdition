"""`whiteboard night show [--no-sky] | hide`: sleep mode's night view on the projector.

Each goes through the daemon's /api/night routes, like the board_night_* MCP tools.
tools/sleepmode calls the same routes itself when sleep mode starts and ends; this
command is for trying the view by hand. Like the board commands, it starts the daemon
if it isn't running.
"""

import argparse
from collections.abc import Mapping
from typing import Any

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection
from whiteboard.config import Settings

NIGHT_ACTIONS = ("show", "hide")
# display.scene's NIGHT_VIEW, not imported: display pulls in numpy, and the CLI starts quick.
NIGHT_VIEW = "night"


def add_night_arguments(parser: argparse.ArgumentParser) -> None:
    """ACTION [--no-sky]."""
    parser.add_argument("action", choices=NIGHT_ACTIONS, help="show or hide the night view")
    parser.add_argument(
        "--no-sky", action="store_true", help="show: a plain black page instead of the sky"
    )


def run_night(args: argparse.Namespace, settings: Settings) -> int:
    """Send the action to the daemon and print what the board shows now."""
    connection = daemon_connection(args, settings)
    result = connection.call(lambda api: api.night(args.action, sky=not args.no_sky))
    print(describe_night(result))
    return EXIT_OK


def describe_night(result: Mapping[str, Any]) -> str:
    """One line: the view, and under the night view its sky and the view underneath."""
    if result.get("view") != NIGHT_VIEW:
        return f"view: {result.get('view')}"
    sky = "night sky" if result.get("sky") else "plain black"
    return f"view: night ({sky}, seed {result.get('seed')}); hiding: {result.get('previous_view')}"


NIGHT = Command(
    "night",
    "sleep mode's night view: night show [--no-sky] | night hide",
    add_night_arguments,
    run_night,
)
