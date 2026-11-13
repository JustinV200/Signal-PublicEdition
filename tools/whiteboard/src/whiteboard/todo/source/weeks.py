"""Find and read this week's and next week's plans in the owner's KB (life/).

Layout (life/README.md): `life/terms/<term>/weeks/<Monday>-to-<Sunday>/plan.md`, e.g.
`2026-10-19-to-10-25`. Next week's plan only exists once the week has been rolled
over, so it's read when it's there and skipped otherwise.

tools/mail-digest/src/mail_digest/kb/targets.py has its own copy of
week_folder_name. Sharing it through packages/ would mean a new package, lockfile
changes in both tools and a re-sync of the running whiteboard venv, which costs more
than these few lines for now.
TODO: move week_folder_name into a shared packages/ helper (and have both tools
depend on it) the next time either tool's dependencies change anyway.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from whiteboard.todo.source.plan_file import PLAN_FILE, read_plan
from whiteboard.todo.source.plan_lines import PlanEntry, parse_plan, split_recurring

DAYS_PER_WEEK = 7


@dataclass(frozen=True)
class WeekPlan:
    """One week's plan file.

    Attributes:
        week: The week's folder name, e.g. "2026-10-19-to-10-25".
        monday: The week's Monday, for weekday-only due dates.
        path: The plan.md file.
    """

    week: str
    monday: date
    path: Path


def week_folder_name(day: date) -> str:
    """The KB's folder name for day's Monday-to-Sunday week, e.g. 2026-10-19-to-10-25.

    The Sunday drops its year, so 2026-12-28-to-01-03 ends in the next year. Names
    start with the Monday's full date, so they sort by date as text.
    """
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=DAYS_PER_WEEK - 1)
    return f"{monday.isoformat()}-to-{sunday:%m-%d}"


def find_week_plans(life_dir: Path, today: date) -> list[WeekPlan]:
    """This week's and next week's plan.md, the ones that exist, in that order."""
    plans = []
    for day in (today, today + timedelta(days=DAYS_PER_WEEK)):
        week = week_folder_name(day)
        matches = sorted((life_dir / "terms").glob(f"*/weeks/{week}/{PLAN_FILE}"))
        if matches:
            monday = day - timedelta(days=day.weekday())
            plans.append(WeekPlan(week, monday, matches[0]))
    return plans


def read_week_entries(life_dir: Path, today: date) -> tuple[list[PlanEntry], list[WeekPlan]]:
    """Parse the todo lines of this week's and next week's plans.

    Returns:
        (entries in plan order, this week's first, with recurring items split by
        date; the plans that were read).

    Raises:
        OSError: A plan exists but can't be read.
        UnicodeDecodeError: A plan isn't UTF-8.
    """
    plans = find_week_plans(life_dir, today)
    entries: list[PlanEntry] = []
    for plan in plans:
        entries += parse_plan(read_plan(plan.path).text, plan.path, plan.monday)
    return split_recurring(entries), plans
