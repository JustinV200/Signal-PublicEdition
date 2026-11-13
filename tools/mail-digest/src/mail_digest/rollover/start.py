"""Starts a week folder: its skeleton files, and the very first week of a new life/.

Every new week gets a workspace README, log.md and review.md (week_files). The first
week has no earlier plan to carry from, so first_week_writes starts it from the plan
template alone. The caller asks uses_life first: only a life/ with an inbox.md (the
owner's sign they use it) gets a first week, so an unused life/ gets nothing written.
"""

import logging
from pathlib import Path

from mail_digest.rollover.templates import fill_template
from mail_digest.rollover.terms import covering_term, has_ended, term_dirs
from mail_digest.rollover.weeks import PLAN_FILE, TERMS_DIR, Week

log = logging.getLogger(__name__)

WORKSPACE_README = "Scratch files and info needed for the week of Mon {monday} to Sun {sunday}.\n"
# Its presence opts life/ in to starting the first week.
INBOX_FILE = "inbox.md"


def week_files(life_dir: Path, week_dir: Path, week: Week) -> dict[Path, str]:
    """The week's workspace README, log and review, the ones that don't exist yet.

    Raises TemplateError for a broken template, OSError if one can't be read.
    """
    files = {
        week_dir / "workspace" / "README.md": WORKSPACE_README.format(
            monday=week.monday.isoformat(), sunday=week.sunday.isoformat()
        ),
        week_dir / "log.md": fill_template(life_dir, "log", week),
        week_dir / "review.md": fill_template(life_dir, "review", week),
    }
    return {path: text for path, text in files.items() if not path.exists()}


def uses_life(life_dir: Path) -> bool:
    """True if life/ has an inbox.md, the owner's opt-in to starting the first week."""
    return (life_dir / INBOX_FILE).is_file()


def first_week_writes(life_dir: Path, week: Week) -> dict[Path, str] | None:
    """Every file that starts the first week, plan.md last, or None between terms.

    Only for a week with no plan and no earlier plan, in a life/ that uses_life (the
    caller checks both). None if no term can take the week. Raises like week_files.
    """
    term_writes = _first_term(life_dir, week)
    if term_writes is None:
        return None
    term_dir, writes = term_writes
    week_dir = term_dir / "weeks" / week.name
    writes |= week_files(life_dir, week_dir, week)
    writes[week_dir / PLAN_FILE] = fill_template(life_dir, "plan", week)
    return writes


def _first_term(life_dir: Path, week: Week) -> tuple[Path, dict[Path, str]] | None:
    """The first week's term folder and its README to create, if any; None between terms.

    The term whose dates cover the week, else the only term folder unless its dates
    say it has ended, else (none at all) a new terms/<year>/ with a one-line README.
    An ended only term, or several term folders none covering the week, is between
    terms (logged), so the runner's between-terms notice asks for a Term dates line.
    """
    covering = covering_term(life_dir, week)
    if covering:
        return covering, {}
    terms = term_dirs(life_dir)
    if not terms:
        year_dir = life_dir / TERMS_DIR / str(week.monday.year)
        return year_dir, {year_dir / "README.md": f"# {week.monday.year}\n"}
    if len(terms) == 1 and not has_ended(terms[0], week):
        return terms[0], {}
    log.warning("can't start the first week %s: no term folder's Term dates cover it", week.name)
    return None
