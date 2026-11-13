"""Picks the term folder a new week goes in.

A term README (life/terms/<term>/README.md) may say when the term runs, on a line
of its own: `Term dates: 2026-08-24 to 2026-12-18`. Terms without that line have no
known end. The rules, safest first:

1. A term whose dates overlap the week gets it (the latest-starting one, if two do).
2. Otherwise the week stays in the term of the plan it carries from, unless that
   term's dates say it has ended.
3. Otherwise the week falls between terms: no term gets it and the rollover stops.
   The next term folder (and its courses) is the owner's to create; only the very
   first week (start.py) may create a term, and only when life/ has none.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mail_digest.rollover.weeks import TERMS_DIR, Week

log = logging.getLogger(__name__)

TERM_DATES = re.compile(
    r"^Term dates: (?P<start>\d{4}-\d{2}-\d{2}) to (?P<end>\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class TermDates:
    """A term's first and last day."""

    start: date
    end: date


def read_term_dates(term_dir: Path) -> TermDates | None:
    """The term's dates from its README, or None if it has no valid `Term dates:` line.

    An unreadable README or an impossible date is logged and treated as no dates.
    """
    readme = term_dir / "README.md"
    if not readme.is_file():
        return None
    try:
        match = TERM_DATES.search(readme.read_text(encoding="utf-8"))
        if not match:
            return None
        return TermDates(date.fromisoformat(match["start"]), date.fromisoformat(match["end"]))
    except (OSError, UnicodeDecodeError, ValueError):
        log.exception("ignoring the term dates of %s", term_dir.name)
        return None


def pick_term(life_dir: Path, source_term: Path, week: Week) -> Path | None:
    """The term folder `week` belongs in (rules in the module docstring), or None between terms.

    source_term: the term folder of the plan the week carries from.
    """
    covering = covering_term(life_dir, week)
    if covering:
        return covering
    return None if has_ended(source_term, week) else source_term


def has_ended(term_dir: Path, week: Week) -> bool:
    """True if the term's `Term dates:` say it ended before `week` (no dates: never)."""
    dates = read_term_dates(term_dir)
    return bool(dates and dates.end < week.monday)


def term_dirs(life_dir: Path) -> list[Path]:
    """Every term folder in life/, sorted (none if life/terms/ doesn't exist)."""
    terms_dir = life_dir / TERMS_DIR
    return sorted(p for p in terms_dir.iterdir() if p.is_dir()) if terms_dir.is_dir() else []


def covering_term(life_dir: Path, week: Week) -> Path | None:
    """The term folder whose `Term dates:` overlap `week` (the latest-starting one), or None."""
    covering = []
    for term_dir in term_dirs(life_dir):
        dates = read_term_dates(term_dir)
        if dates and dates.start <= week.sunday and dates.end >= week.monday:
            covering.append((dates.start, term_dir))
    return max(covering)[1] if covering else None
