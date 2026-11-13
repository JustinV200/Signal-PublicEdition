"""`mail-digest` entry point: parses the flags, sets up logging and runs under the lock.

- `mail-digest`: one run in the foreground (what the scheduled 07:00 task runs). It
  must stay email-only and never do anything that could trigger Duo: the owner is
  asleep then. Duo-capable steps belong to on-demand runs only (see README).
- `mail-digest --now`: start that run in the background and return at once.
- `mail-digest --dry-run`: log the command and run context only.

Logs go to the gitignored log file (and to stderr when there is a console).
"""

import argparse
import logging
from collections.abc import Sequence

from mail_digest.digest.deps import default_deps
from mail_digest.digest.run import run_once
from mail_digest.memory import LockHeldError, run_lock
from mail_digest.settings import LOCK_PATH, LOG_PATH
from mail_digest.steps import setup_logging, start_background_run

log = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command. Returns 0 on success, 1 on any failure (logged)."""
    args = _parse_args(argv)
    if args.now:
        return start_background_run(LOCK_PATH)
    setup_logging(LOG_PATH)
    try:
        with run_lock(LOCK_PATH):
            return run_once(default_deps(), dry_run=args.dry_run)
    except LockHeldError:
        log.error("another mail digest run is in progress; not starting this one")
        return 1
    except Exception:
        # run_once counts its own crashes as failed runs. What gets here is outside
        # it (the lock file can't be opened) or a crash it couldn't record.
        log.exception("mail digest run crashed")
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """The command-line flags (--now and --dry-run exclude each other)."""
    parser = argparse.ArgumentParser(prog="mail-digest", description="Digest Gmail into life/.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--now",
        action="store_true",
        help="start a run in the background and return at once (refused if one is running)",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="log the command line and run context, but don't run claude or touch the state",
    )
    return parser.parse_args(argv)
