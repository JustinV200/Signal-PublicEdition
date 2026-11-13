"""Week math and week-folder lookups for the rollover.

Layout (life/README.md): terms/<term>/weeks/<Monday>-to-<Sunday>/plan.md. A week
counts as rolled over once its plan.md exists; a folder with only workspace/ in it
(someone saved scratch files early) doesn't.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from mail_digest.kb import week_folder_name

PLAN_FILE = "plan.md"
# life/<TERMS_DIR>/<term>/ holds every term folder.
TERMS_DIR = "terms"
DAYS_PER_WEEK = 7


@dataclass(frozen=True)
class Week:
    """One Monday-to-Sunday week.

    monday: the week's Monday.
    name: its folder name, e.g. "2026-10-19-to-10-25".
    """

    monday: date
    name: str

    @property
    def sunday(self) -> date:
        """The week's last day."""
        return self.monday + timedelta(days=DAYS_PER_WEEK - 1)

    def day(self, offset: int) -> date:
        """The week's day `offset` days after Monday (0 = Monday)."""
        return self.monday + timedelta(days=offset)


def week_of(day: date) -> Week:
    """The week holding `day`."""
    monday = day - timedelta(days=day.weekday())
    return Week(monday, week_folder_name(monday))


def week_from_folder(name: str) -> Week:
    """The week a folder name stands for. Raises ValueError if it doesn't start with a date."""
    return week_of(date.fromisoformat(name[:10]))


def find_plan_dir(life_dir: Path, week: Week) -> Path | None:
    """The week's folder if any term has its plan.md, else None."""
    plans = sorted((life_dir / TERMS_DIR).glob(f"*/weeks/{week.name}/{PLAN_FILE}"))
    return plans[0].parent if plans else None


def latest_plan_dir_before(life_dir: Path, week: Week) -> Path | None:
    """The newest week folder before `week` that has a plan.md, across every term.

    Week names start with their Monday's date, so they sort by date as text, unlike
    term names (2026-fall sorts before 2026-spring).
    """
    dirs = [
        plan.parent
        for plan in (life_dir / TERMS_DIR).glob(f"*/weeks/*/{PLAN_FILE}")
        if plan.is_file() and plan.parent.name < week.name
    ]
    return max(dirs, key=lambda folder: folder.name) if dirs else None
