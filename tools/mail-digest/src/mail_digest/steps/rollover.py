"""Rolls life/ over to today's week at the start of a run, before anything reads the week.

So the week's first digest already finds, edits and emails the new week's plan, and
the whiteboard sync after it shows that week. It runs before the KB snapshot, so the
guard never takes the new files for the model's work. A failed rollover doesn't stop
the run (readers fall back to last week's plan), but it, and a week that falls
between terms, comes back as a notice the runner speaks with its other
announcements. The notice is keyed by week, so it's spoken once a week at most.
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mail_digest.announce import Announcement
from mail_digest.kb import week_folder_name
from mail_digest.rollover import BETWEEN_TERMS, describe, roll_over

log = logging.getLogger(__name__)

# roll_week's status when roll_over raised (the others are roll_over's).
FAILED = "failed"
FAILED_SENTENCE = "The week rollover couldn't start this week's plan. Check the run's log."
BETWEEN_TERMS_SENTENCE = (
    "The week rollover stopped because the term has ended. Add the next term's folder "
    "under life/terms with a Term dates line, and it will carry on."
)


@dataclass(frozen=True)
class WeekRoll:
    """How a run's rollover went.

    status: roll_over's status, or FAILED. notice: what to announce, or None.
    """

    status: str
    notice: Announcement | None = None


def roll_week(life_dir: Path, today: date, dry_run: bool = False) -> WeekRoll:
    """Roll life/ over to today's week (writes nothing on a dry run). Never raises.

    A dry run makes no notice.
    """
    week = week_folder_name(today)
    try:
        result = roll_over(life_dir, today, dry_run=dry_run)
    except (OSError, ValueError):
        log.exception("week rollover failed; the run goes on with the existing weeks")
        return WeekRoll(FAILED, _notice(week, FAILED, FAILED_SENTENCE, dry_run))
    log.info("%s%s", "dry run, " if dry_run else "", describe(result))
    if result.status == BETWEEN_TERMS:
        log.warning("week %s falls between terms; add the next term's folder", week)
        return WeekRoll(result.status, _notice(week, "term", BETWEEN_TERMS_SENTENCE, dry_run))
    return WeekRoll(result.status)


def _notice(week: str, kind: str, sentence: str, dry_run: bool) -> Announcement | None:
    """The week's rollover notice (`rollover|<week>|<kind>`), or None on a dry run."""
    return None if dry_run else Announcement(f"rollover|{week}|{kind}", sentence)
