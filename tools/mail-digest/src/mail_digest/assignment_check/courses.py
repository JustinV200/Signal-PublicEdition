"""The checker's courses and the fixed pages it visits for each.

The courses, site addresses and Classroom account come from the owner's gitignored
assignment-check.toml (check_config.py loads it; setup writes it). Each course gets a
few index pages (design section 4), which become one visit plan per site: Classroom
first, then Moodle. The page's course tag and list kind come from here, never from a
model.

Site details marked DRAFT [unverified] are the design's best guesses; check them on
your own sites and correct them here.
"""

import json
from dataclasses import dataclass

MOODLE = "moodle"
CLASSROOM = "classroom"
SITES = (MOODLE, CLASSROOM)
# Classroom runs first, so its results are in even if the owner walks away during
# the Moodle login. The readers run Moodle first (design section 3.2).
VISIT_ORDER = (CLASSROOM, MOODLE)
READ_ORDER = (MOODLE, CLASSROOM)
SITE_NAMES = {MOODLE: "Moodle", CLASSROOM: "Classroom"}

# Moodle's index pages: every assignment (with its status), quizzes, other due events.
MOODLE_LISTS = {
    "assign": "/mod/assign/index.php?id={course}",
    "quiz": "/mod/quiz/index.php?id={course}",
    "calendar": "/calendar/view.php?view=upcoming&course={course}",
}
# DRAFT [unverified]: Classroom's per-class to-do lists. If only the /all forms work,
# use those; the class name check in findings/ then does the filtering.
CLASSROOM_LISTS = {
    "not-turned-in": "/a/not-turned-in/{course}",
    "missing": "/a/missing/{course}",
    "turned-in": "/a/turned-in/{course}",
}


@dataclass(frozen=True)
class Course:
    """One course: its life/ tag, site and site id, and (Classroom) the class name.

    class_name is the class as Classroom shows it; findings/ matches the reader's
    class_name against it.
    """

    tag: str
    site: str
    site_id: str
    class_name: str = ""


@dataclass(frozen=True)
class CheckConfig:
    """The owner's sites and courses (from assignment-check.toml).

    moodle_base and classroom_base are https origins (plus Classroom's /u/N account
    slot), with no trailing slash. classroom_account is the school Google account a
    Classroom page must show.
    """

    moodle_base: str
    classroom_base: str
    classroom_account: str
    courses: tuple[Course, ...]


@dataclass(frozen=True)
class Page:
    """One page to visit: its plan key, URL and site, its course and list kind, the site's
    base URL (item links are rebuilt on it) and, on Classroom, the account it must show."""

    key: str
    url: str
    site: str
    course: Course
    list_kind: str
    base: str
    account: str = ""


def site_pages(site: str, config: CheckConfig) -> tuple[Page, ...]:
    """Every page to visit on site, course by course, in a fixed order."""
    is_moodle = site == MOODLE
    base = config.moodle_base if is_moodle else config.classroom_base
    lists = MOODLE_LISTS if is_moodle else CLASSROOM_LISTS
    account = "" if is_moodle else config.classroom_account
    return tuple(
        Page(
            key=f"{course.tag}-{kind}",
            url=base + path.format(course=course.site_id),
            site=site,
            course=course,
            list_kind=kind,
            base=base,
            account=account,
        )
        for course in config.courses
        if course.site == site
        for kind, path in lists.items()
    )


def plan_json(pages: tuple[Page, ...]) -> str:
    """The browser-tool-visit plan file for one launch's pages."""
    targets = [{"key": page.key, "url": page.url, "site": page.site} for page in pages]
    return json.dumps({"targets": targets}, indent=1)
