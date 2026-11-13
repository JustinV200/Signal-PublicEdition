"""`whiteboard idle show|hide|sync`: the idle view, the board's default when nothing is drawn.

Each goes through the daemon's /api/idle routes, like the board_idle_* MCP tools. The
daemon switches to the idle view by itself once the items view has been empty for
[idle] empty_s, so this is for showing it now, leaving it, or refreshing every source
(files, weather, news) at once. Like the board commands, it starts the daemon if it
isn't running.
"""

import argparse
from collections.abc import Mapping
from typing import Any

from whiteboard.cli.command import EXIT_OK, Command, daemon_connection
from whiteboard.config import Settings

IDLE_ACTIONS = ("show", "hide", "sync")


def add_idle_arguments(parser: argparse.ArgumentParser) -> None:
    """ACTION."""
    parser.add_argument("action", choices=IDLE_ACTIONS, help="what to do with the idle view")


def run_idle(args: argparse.Namespace, settings: Settings) -> int:
    """Send the action to the daemon and print what the view shows now."""
    connection = daemon_connection(args, settings)
    print(describe_idle(connection.call(lambda api: api.idle(args.action))))
    return EXIT_OK


def describe_idle(result: Mapping[str, Any]) -> str:
    """One line: the view, then the count in each region."""
    weather = result.get("weather") or "unavailable"
    place = f" ({result['place']})" if result.get("place") else ""
    headline = "yes" if result.get("headline") else "none"
    return (
        f"view: {result.get('view')}; today {result.get('tasks')}, "
        f"priorities {result.get('priorities')}, agents {result.get('agents_active')}, "
        f"upcoming {result.get('upcoming')}; weather {weather}{place}; headline {headline}"
    )


IDLE = Command(
    "idle",
    "the idle view (clock, tasks, weather, news): idle show | hide | sync",
    add_idle_arguments,
    run_idle,
)
