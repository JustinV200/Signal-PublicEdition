"""`mail-digest rollover`: roll life/ over to this week by hand, outside a digest run.

    mail-digest rollover [--dry-run] [--date YYYY-MM-DD] [--life-dir PATH]

--dry-run prints the files it would create and their text and writes nothing.
--date and --life-dir are for trying it on another day or on a copy of life/. A
real run takes the digest's run lock, so it never races a digest run.
"""

import argparse
import logging
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from mail_digest.memory import LockHeldError, run_lock
from mail_digest.rollover import describe, roll_over
from mail_digest.settings import LIFE_DIR, LOCK_PATH, LOG_PATH
from mail_digest.steps import setup_logging

log = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command. Returns 0 on success, 1 on failure (logged)."""
    args = _parse_args(argv)
    setup_logging(LOG_PATH)
    try:
        if args.dry_run:
            result = roll_over(args.life_dir, args.date, dry_run=True)
        else:
            with run_lock(LOCK_PATH):
                result = roll_over(args.life_dir, args.date)
    except LockHeldError:
        log.error("a mail digest run is in progress; it rolls the week over itself")
        return 1
    except (OSError, ValueError):
        log.exception("week rollover failed")
        return 1
    log.info("%s", describe(result))
    if args.dry_run:
        for relative, text in result.writes:
            print(f"--- would write {relative}\n{text}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """The rollover's flags."""
    parser = argparse.ArgumentParser(
        prog="mail-digest rollover", description="Roll life/ over to this week."
    )
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    parser.add_argument(
        "--date", type=date.fromisoformat, default=date.today(), help="roll to this day's week"
    )
    parser.add_argument("--life-dir", type=Path, default=LIFE_DIR, help="the life/ to roll")
    return parser.parse_args(argv)
