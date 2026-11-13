"""`whiteboard todo sync|show|hide|done|undone`: the TODO view on the projector.

Each goes through the daemon's /api/todo routes, like the board_todo_* MCP tools.
`sync --if-running` is what the 06:00 scheduled task runs (tools/whiteboard/schedule/):
it refreshes a running daemon and does nothing otherwise, so it never lights the
projector by itself (a daemon syncs anyway when it starts).
"""

import argparse
import sys
from collections.abc import Mapping
from typing import Any

from whiteboard.cli.command import EXIT_OK, EXIT_USER_ERROR, Command, daemon_connection
from whiteboard.config import Settings
from whiteboard.daemon_client import DaemonStartError

TODO_ACTIONS = ("sync", "show", "hide", "done", "undone")
ITEM_ACTIONS = ("done", "undone")


def add_todo_arguments(parser: argparse.ArgumentParser) -> None:
    """ACTION [ITEM] [--if-running]."""
    parser.add_argument("action", choices=TODO_ACTIONS, help="what to do with the TODO view")
    parser.add_argument(
        "item", nargs="?", default=None, help="done/undone: the item's id or a piece of its text"
    )
    parser.add_argument(
        "--if-running",
        action="store_true",
        help="don't start the daemon; if it isn't running, do nothing (the daily sync)",
    )


def run_todo(args: argparse.Namespace, settings: Settings) -> int:
    """Send the action to the daemon and print what the view shows now."""
    if (args.action in ITEM_ACTIONS) != (args.item is not None):
        print(f"whiteboard: error: only {' and '.join(ITEM_ACTIONS)} take an ITEM", file=sys.stderr)
        return EXIT_USER_ERROR
    connection = daemon_connection(args, settings, is_auto_start=not args.if_running)
    try:
        result = connection.call(lambda api: api.todo(args.action, args.item))
    except DaemonStartError:
        if not args.if_running:
            raise
        print("whiteboard daemon isn't running; it syncs the TODO view when it starts")
        return EXIT_OK
    print(describe_todo(result))
    return EXIT_OK


def describe_todo(result: Mapping[str, Any]) -> str:
    """A few lines: which view shows, the counts, what changed, then one line per item."""
    if "items" not in result:
        return f"view: {result.get('view')}"
    lines = []
    if result.get("item"):
        item = result["item"]
        verb = "changed" if result.get("changed") else "already so, nothing changed"
        lines.append(f"[{item['tag']}] {item['text']}: {verb}")
    lines.append(
        f"view: {result.get('view')}; {result.get('overdue')} overdue, "
        f"{result.get('upcoming')} due soon, {result.get('of_note')} of note, "
        f"{len(result.get('newly_done', []))} newly done; plans: "
        f"{', '.join(result.get('plans', [])) or 'none'}"
    )
    for item in result["items"]:
        mark = "x" if item.get("done") else " "
        due = f" (due {item['due']})" if item.get("due") else ""
        lines.append(f"  {item['id']}  [{mark}] [{item['tag']}] {item['text']}{due}")
    return "\n".join(lines)


TODO = Command(
    "todo",
    "the TODO view: todo sync|show|hide [--if-running], todo done|undone ITEM",
    add_todo_arguments,
    run_todo,
)
