"""`whiteboard keynotes`: write today's keynotes now, then refresh a running daemon.

The 06:00 scheduled task runs it (tools/whiteboard/schedule/), and it works on demand.
It calls Claude once (whiteboard.keynotes), writes .state/keynotes.json, prints the
lines, then asks a running daemon for a TODO sync so the TODO view shows them; the
idle view picks the file up by itself within a few seconds. It never starts the
daemon or lights the projector.
"""

import argparse
import asyncio
import sys
from datetime import date

from whiteboard.cli.command import EXIT_FAILED, EXIT_OK, Command, daemon_connection, no_arguments
from whiteboard.config import LIFE_DIR, STATE_DIR, Settings
from whiteboard.daemon_client import DaemonStartError

# The TODO view's done-tracking, so items ticked before today are left out (read-only).
TODO_STATE_FILE = "todo.json"


def run_keynotes(args: argparse.Namespace, settings: Settings) -> int:
    """Generate and save today's keynotes, print them, and refresh a running daemon."""
    from whiteboard.keynotes import KEYNOTES_FILE, generate_keynotes

    paths = (STATE_DIR / TODO_STATE_FILE, STATE_DIR / KEYNOTES_FILE)
    try:
        lines = asyncio.run(generate_keynotes(LIFE_DIR, date.today(), paths))
    except Exception as error:
        # Like the board's triage: a missing or failing Claude CLI (any SDK error), a bad
        # reply or an unreadable plan is one line, never a traceback in the task's log.
        print(f"whiteboard: keynotes not written: {error!r}", file=sys.stderr)
        return EXIT_FAILED
    print("\n".join(lines))
    try:
        daemon_connection(args, settings, is_auto_start=False).call(
            lambda api: api.todo("sync", None)
        )
    except DaemonStartError:
        print("(daemon not running; the views show these when it starts)")
    return EXIT_OK


KEYNOTES = Command(
    "keynotes",
    "write today's keynotes with Claude now (also the 06:00 task's first step)",
    no_arguments,
    run_keynotes,
)
