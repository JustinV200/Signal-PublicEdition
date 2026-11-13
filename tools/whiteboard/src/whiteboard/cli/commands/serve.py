"""`whiteboard serve | stop`: run the daemon in this terminal, or stop a running one.

serve runs until Ctrl+C (or `whiteboard stop`), then closes the kiosk and
releases the camera. stop is how to end a daemon the MCP server started
detached, since that one has no console to press Ctrl+C in.
"""

import argparse
import asyncio
import atexit
import faulthandler
import logging
import os

from whiteboard.cli.command import EXIT_FAILED, EXIT_OK, Command, no_arguments
from whiteboard.config import STATE_DIR, Settings
from whiteboard.daemon_client import DaemonLocation, find_daemon

logger = logging.getLogger(__name__)


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


SERVE = Command(
    "serve", "run the daemon: board page, kiosk, camera, watcher, agent", no_arguments, run_serve
)
STOP = Command(
    "stop", "stop a running daemon (closes the kiosk, frees the camera)", no_arguments, run_stop
)
