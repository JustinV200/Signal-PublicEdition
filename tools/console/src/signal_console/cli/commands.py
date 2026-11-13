"""The `console` subcommands other than `open`: serve, claim and hub start|stop|status.

Each takes the parsed arguments and returns an exit code; errors propagate to
cli/main.py, which prints them.
"""

import argparse
import asyncio
import contextlib
import os

from signal_console.hub import find_console_hub, start_hub, stop_hub
from signal_console.orchestrator import claim_from_env, write_claim
from signal_console.paths import HUB_LOG_FILE, STATE_DIR, WEB_DIST_DIR
from signal_console.server import serve
from signal_console.status import is_hub_listening


def run_serve(args: argparse.Namespace) -> int:
    """Run the server in the foreground until Ctrl+C."""
    # Ctrl+C is how a foreground server is meant to stop.
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(args.port, STATE_DIR, WEB_DIST_DIR))
    return 0


def run_claim(args: argparse.Namespace) -> int:
    """Make the calling Claude Code session the console's orchestrator."""
    claim = claim_from_env(os.environ, args.label)
    write_claim(STATE_DIR, claim)
    named = f" as {claim.label!r}" if claim.label else ""
    print(f"This session is now the console's orchestrator{named}.")
    return 0


def run_hub(args: argparse.Namespace) -> int:
    """Start, stop or report the voice hub."""
    if args.hub_command == "start":
        record = start_hub(STATE_DIR)
        print(f"Voice hub starting (pid {record.pid}); output in {STATE_DIR / HUB_LOG_FILE}")
    elif args.hub_command == "stop":
        print(
            "Voice hub stopped."
            if stop_hub(STATE_DIR)
            else "No voice hub the console can stop is running."
        )
    else:
        print(_describe_hub())
    return 0


def _describe_hub() -> str:
    process = find_console_hub(STATE_DIR)
    if asyncio.run(is_hub_listening()):
        started = f"by the console (pid {process.pid})" if process else "outside the console"
        return f"Voice hub running, started {started}."
    if process is not None:
        return f"Voice hub starting (pid {process.pid}), not listening yet."
    return "Voice hub not running."
