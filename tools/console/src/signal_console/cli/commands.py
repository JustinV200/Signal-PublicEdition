"""The `console` subcommands other than `open`: serve, claim and hub start|stop|status.

Each takes the parsed arguments and returns an exit code; errors propagate to
cli/main.py, which prints them.
"""

import argparse
import asyncio
import contextlib
import logging
import os
from datetime import datetime

from signal_console.cli.server_log import log_to_server_log
from signal_console.hub import find_console_hub, start_hub, stop_hub
from signal_console.orchestrator import claim_from_env, default_label, write_claim
from signal_console.paths import HUB_LOG_FILE, STATE_DIR, WEB_DIST_DIR
from signal_console.server import serve
from signal_console.status import is_hub_listening

log = logging.getLogger(__name__)


def run_serve(args: argparse.Namespace) -> int:
    """Run the server in the foreground until Ctrl+C, logging to .state/server.log too.

    Returns 1 when the server couldn't start or stopped on an error (say the port is
    taken), after logging why; under the logon task that shows as the task's last result.
    """
    log_to_server_log(STATE_DIR)
    try:
        # Ctrl+C is how a foreground server is meant to stop.
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(serve(args.port, STATE_DIR, WEB_DIST_DIR))
    except Exception:
        # Under pythonw (the logon task) there's no stderr: the log is the only trace.
        log.exception("The console server on port %d stopped", args.port)
        return 1
    return 0


def run_claim(args: argparse.Namespace) -> int:
    """Make the calling Claude Code session the console's orchestrator, replacing any claim."""
    # With no --label, the local time tells this session from earlier ones.
    claim = claim_from_env(os.environ, args.label or default_label(datetime.now()))
    write_claim(STATE_DIR, claim)
    named = f" as {claim.label!r}" if claim.label else ""
    print(f"This session is now linked to the console{named}.")
    return 0


def run_hub(args: argparse.Namespace) -> int:
    """Start, stop or report the voice hub."""
    if args.hub_command == "start":
        record = start_hub(STATE_DIR)
        print(f"Voice is starting (pid {record.pid}); output in {STATE_DIR / HUB_LOG_FILE}")
    elif args.hub_command == "stop":
        print(
            "Voice stopped."
            if stop_hub(STATE_DIR)
            else "Voice isn't running, so there was nothing to stop."
        )
    else:
        print(_describe_hub())
    return 0


def _describe_hub() -> str:
    process = find_console_hub(STATE_DIR)
    if asyncio.run(is_hub_listening()):
        started = f"by the console (pid {process.pid})" if process else "outside the console"
        return f"Voice is running, started {started}."
    if process is not None:
        return f"Voice is starting (pid {process.pid}), not listening yet."
    return "Voice isn't running."
