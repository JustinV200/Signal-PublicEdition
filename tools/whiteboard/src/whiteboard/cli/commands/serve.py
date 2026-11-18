"""`whiteboard serve | stop | status`: run the daemon here, stop a running one, or ask if one is up.

serve runs until Ctrl+C (or `whiteboard stop`), then closes the kiosk and
releases the camera. stop is how to end a daemon the MCP server started
detached, since that one has no console to press Ctrl+C in. status never
starts one: it's the setup tool's health check.
"""

import argparse
import asyncio
import atexit
import faulthandler
import json
import logging
import os

from whiteboard.cli.command import EXIT_FAILED, EXIT_OK, Command, no_arguments
from whiteboard.config import STATE_DIR, Settings
from whiteboard.daemon_client import DaemonApiError, DaemonLocation, find_daemon

logger = logging.getLogger(__name__)

# Under the setup tool's 300-character cap on a summary field.
MAX_WORDS_CHARS = 200
# `whiteboard stop` can't help here: it finds the daemon the same way and fails the same way.
STALE_DAEMON_FIX = (
    "End the process holding the whiteboard port (see tools/whiteboard/.state/daemon.log); "
    "the next board call starts a fresh one."
)


def run_serve(args: argparse.Namespace, settings: Settings) -> int:
    """Run the daemon until Ctrl+C or a stop request."""
    # Imported here: the daemon pulls in OpenCV, aiohttp and the Agent SDK.
    from whiteboard.daemon import run_daemon

    # A detached daemon's stderr is .state/daemon.log, so a native crash (OpenCV,
    # MSMF) dumps its stacks there, an exit leaves a line, and a log that just
    # stops means the process was killed from outside.
    faulthandler.enable(all_threads=True)
    atexit.register(logger.info, "whiteboard daemon exiting (pid %d)", os.getpid())
    try:
        asyncio.run(run_daemon(settings))
    except Exception:
        logger.exception("whiteboard daemon crashed")
        raise
    return EXIT_OK


def run_stop(args: argparse.Namespace, settings: Settings) -> int:
    """Ask a running daemon to shut down cleanly."""
    api = find_daemon(DaemonLocation(STATE_DIR, settings.display.port))
    if api is None:
        print("no whiteboard daemon is running")
        return EXIT_FAILED
    api.shutdown()
    print("whiteboard daemon is stopping")
    return EXIT_OK


def run_status(args: argparse.Namespace, settings: Settings) -> int:
    """Say whether a daemon answers, without starting one.

    The last stdout line is one JSON object {words, fix, command}, the setup tool's
    check summary (tools/setup/README.md, "Verify checks"). Not running passes: the
    first board call starts the daemon. Exit 1 only when one answers with an error or hangs.
    """
    try:
        api = find_daemon(DaemonLocation(STATE_DIR, settings.display.port))
    except DaemonApiError as error:
        # Something answers but refuses us (a stale token) or hangs: a restart fixes both.
        _print_summary(f"daemon not answering properly: {error}", STALE_DAEMON_FIX)
        return EXIT_FAILED
    if api is None:
        _print_summary("installed, not running (a board call starts it)")
    else:
        _print_summary("running")
    return EXIT_OK


def _print_summary(words: str, fix: str | None = None) -> None:
    """Print the one-line {words, fix, command} summary; words are cut to MAX_WORDS_CHARS."""
    words = " ".join(words.split())
    if len(words) > MAX_WORDS_CHARS:
        words = words[: MAX_WORDS_CHARS - 1] + "…"
    print(json.dumps({"words": words, "fix": fix, "command": None}))


SERVE = Command(
    "serve", "run the daemon: board page, kiosk, camera, watcher, agent", no_arguments, run_serve
)
STOP = Command(
    "stop", "stop a running daemon (closes the kiosk, frees the camera)", no_arguments, run_stop
)
STATUS = Command(
    "status", "say whether the daemon is running (never starts it)", no_arguments, run_status
)
