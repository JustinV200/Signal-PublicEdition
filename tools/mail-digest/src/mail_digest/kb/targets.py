"""Finds the life/ files a run may edit: inbox.md, this week's plan and the current courses.

The job has Read and Edit but no Glob, so the runner looks these up, names them in
the run context and turns them into exact Edit rules. Layout (life/README.md):
terms/<term>/weeks/<Monday>-to-<Sunday>/plan.md (e.g. 2026-10-19-to-10-25) and
terms/<term>/courses/<course>/README.md. Everything is looked up at run time, because
the KB changes (folders get renamed).

tools/whiteboard/src/whiteboard/todo/source/weeks.py has its own copy of
week_folder_name. Sharing it through packages/ would mean a new package, lockfile
changes in both tools and a re-sync of the running whiteboard venv, which costs more
than these few lines for now.
TODO: move week_folder_name into a shared packages/ helper (and have both tools
depend on it) the next time either tool's dependencies change anyway.

Only existing plain files count. An Edit rule for a missing file would also let the
job create files under a folder of that name (rules match gitignore-style), and a
path through a link or junction would escape the guard's snapshot, or life/ itself.
"""

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

INBOX = "inbox.md"
# Paths that are safe inside an Edit(/<path>) permission rule: no glob characters,
# parentheses or spaces. KB names are kebab-case, so a path outside this is skipped.
SAFE_PATH = re.compile(r"[A-Za-z0-9._/-]+")
# A week folder runs Monday to Sunday.
DAYS_PER_WEEK = 7


@dataclass(frozen=True)
class KbTargets:
    """Paths relative to life/, in POSIX form (how the job's Edit rules name them).

    week: the week's folder name, e.g. "2026-10-19-to-10-25".
    inbox: "inbox.md", or None if it isn't a plain file.
    plan: this week's plan, or None if the week hasn't been rolled over yet.
    courses: course READMEs of the term holding the latest week up to this one.
    """

    week: str
    inbox: str | None
    plan: str | None
    courses: tuple[str, ...]

    @property
    def editable(self) -> tuple[str, ...]:
        """Every file the run may edit: inbox.md and the plan (if they exist) and the courses."""
        return (*[p for p in (self.inbox, self.plan) if p], *self.courses)


def week_folder_name(day: date) -> str:
    """The KB's folder name for day's Monday-to-Sunday week, e.g. 2026-10-19-to-10-25.

    The Sunday drops its year, so 2026-12-28-to-01-03 ends in the next year. Names
    start with the Monday's full date, so they sort by date as text.
    """
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=DAYS_PER_WEEK - 1)
    return f"{monday.isoformat()}-to-{sunday:%m-%d}"


def find_targets(life_dir: Path, day: date) -> KbTargets:
    """Look up inbox.md, this week's plan and the current term's courses (plain files only)."""
    week = week_folder_name(day)
    inbox = _relative(life_dir, [life_dir / INBOX])
    term_dir = _current_term(life_dir, week)
    courses = _relative(life_dir, term_dir.glob("courses/*/README.md")) if term_dir else []
    return KbTargets(
        week=week,
        inbox=inbox[0] if inbox else None,
        plan=find_plan(life_dir, day),
        courses=tuple(courses),
    )


def find_plan(life_dir: Path, day: date) -> str | None:
    """The plan of day's week, relative to life/, or None if that week isn't rolled over yet.

    The digest email also reads next week's plan through this (digest_email/).
    """
    week = week_folder_name(day)
    plans = _relative(life_dir, (life_dir / "terms").glob(f"*/weeks/{week}/plan.md"))
    return plans[0] if plans else None


def _relative(life_dir: Path, paths: Iterable[Path]) -> list[str]:
    """Sorted POSIX paths relative to life/ of the files that can be targets.

    Skips (and logs) names that aren't SAFE_PATH and paths through a link.
    """
    relative = sorted(p.relative_to(life_dir).as_posix() for p in paths if p.is_file())
    skipped = [p for p in relative if not SAFE_PATH.fullmatch(p) or _is_linked(life_dir, p)]
    if skipped:
        log.warning("skipping KB files that can't be an exact, unlinked Edit rule: %s", skipped)
    return [p for p in relative if p not in skipped]


def _is_linked(life_dir: Path, relative: str) -> bool:
    """True if life_dir/relative resolves somewhere else (a link or junction on the way).

    Compared with normcase, since Windows names are case-insensitive.
    """
    resolved = os.path.realpath(life_dir / relative)
    expected = os.path.join(os.path.realpath(life_dir), relative)
    return os.path.normcase(resolved) != os.path.normcase(expected)


def _current_term(life_dir: Path, week: str) -> Path | None:
    """The term folder holding the latest week folder up to `week`.

    Week names start with their Monday's date, so they sort correctly as text, unlike
    term names (2026-fall sorts before 2026-spring).
    """
    weeks = [w for w in (life_dir / "terms").glob("*/weeks/*") if w.is_dir() and w.name <= week]
    if not weeks:
        return None
    return max(weeks, key=lambda w: w.name).parents[1]
