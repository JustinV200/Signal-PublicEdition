"""`assignment-check` entry point: parses the flags, sets up logging and runs under the lock.

- `assignment-check --now`: start a check in the background and return at once (what
  the voice brain runs when the owner asks to check the owner's assignments).
- `assignment-check`: one check in the foreground, printing the items with their links.
- `assignment-check --dry-run`: print both visit plans and every argv; starts nothing.
- `assignment-check --sign-in-test`: open each site's first page once (setup's sign-in check).

Only the owner starts a check: it opens the vault's Allow dialog and can send a Duo
push. It is never scheduled. It takes the same run lock as the mail digest, since
both edit the same life/ files.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from mail_digest.assignment_check.check_config import CheckConfigError, load_check_config
from mail_digest.assignment_check.live import default_deps, dry_run_lines
from mail_digest.assignment_check.run import run_check
from mail_digest.assignment_check.sign_in_test import sign_in_test
from mail_digest.memory import LockHeldError, run_lock
from mail_digest.settings import CHECK_CONFIG_PATH, CHECK_LOG_PATH, LOCK_PATH
from mail_digest.steps import background_command, setup_logging, start_background_run

log = logging.getLogger(__name__)

MODULE = "mail_digest.assignment_check"
LOCK_HELD = "A mail digest or assignment check is running; try again in a minute."


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command. Returns 0 on success, 1 on any failure (logged)."""
    args = _parse_args(argv)
    if args.now:
        return start_background_run(
            LOCK_PATH, background_command(MODULE), "assignment check", CHECK_LOG_PATH
        )
    try:
        if args.dry_run:
            _print(dry_run_lines())
            return 0
        if args.sign_in_test:
            is_ok, lines = sign_in_test(load_check_config(CHECK_CONFIG_PATH))
            _print(lines)
            return 0 if is_ok else 1
        deps = default_deps()
    except CheckConfigError as error:
        _print([f"assignment check config: {error}"])
        return 1
    setup_logging(CHECK_LOG_PATH)
    try:
        with run_lock(LOCK_PATH):
            outcome = run_check(deps)
    except LockHeldError:
        log.error(LOCK_HELD)
        return 1
    except Exception:
        # run_check speaks its own crashes. What gets here is outside it (the lock
        # file can't be opened).
        log.exception("assignment check crashed")
        return 1
    _print(list(outcome.lines))
    return outcome.exit_code


def _print(lines: list[str]) -> None:
    """Print lines for the owner; a background run (pythonw) has no stdout, so nothing."""
    if sys.stdout is not None:
        print("\n".join(lines))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """The command-line flags (--now and --dry-run exclude each other)."""
    parser = argparse.ArgumentParser(
        prog="assignment-check", description="Check Moodle and Google Classroom into life/."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--now",
        action="store_true",
        help="start a check in the background and return at once (refused if a run is going)",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print both visit plans and every argv, but start nothing",
    )
    mode.add_argument(
        "--sign-in-test",
        action="store_true",
        help="open each site's first page once to check the sign-in; no model runs",
    )
    return parser.parse_args(argv)
