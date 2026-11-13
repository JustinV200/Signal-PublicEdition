"""Tests for mail_digest.rollover: carry-over, idempotency, catch-up and term boundaries.

Every test builds its own life/ in a temp dir; none touches the real one.
"""

from datetime import date

import pytest

from mail_digest.rollover import roll_over

PLAN_TEMPLATE = """# Week plan (Mon <date> to Sun <date>)
## Overdue

## Priorities
1. TODO

## CHEM 120
- [ ] [chem-120] fill from the course site

## Garden
- [ ] [garden] fill from backlog
"""
REVIEW_TEMPLATE = (
    "# Week review (Mon <date> to Sun <date>)\n\n"
    "## Done\n\n## Slipped\n\n## Carried over\n\n## Notes\n"
)
LOG_TEMPLATE = "# Week log (Mon <date> to Sun <date>)\n\n## Mon <date>\n\n## Sun <date>\n"
OLD_PLAN = """# Week plan (Mon 2026-11-02 to Sun 2026-11-08)

## Overdue
- [ ] [hist-205] Memo (was due 2026-10-26 08:30; carried; late)
- [ ] [hist-205] Lab 2 (was due 2026-10-14; carried from 10-12)
- [x] [chem-120] Lab 5 (was due 2026-10-08)

## CHEM 120
- [ ] [chem-120] A30 Titration (due 2026-11-04; posted 2026-11-02) (mail)
- [ ] [chem-120] Lab 8 (due 2026-11-12 10:00) (site)
  - pre-lab first (due 2026-11-01)
- [ ] [chem-120] Typo date (due 2026-02-30)
- [x] [chem-120] A29 (due 2026-11-03)

## Garden
- [ ] [garden] fill from backlog

## Errands
- [ ] [errands] Pick up the package (mail)
"""
OLD = "terms/2026-fall/weeks/2026-11-02-to-11-08"
NEW = "terms/2026-fall/weeks/2026-11-09-to-11-15"


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def life(tmp_path):
    """A life/ with the week templates and the 2026-11-02 week (blank review)."""
    _write(tmp_path, "templates/week-plan.md", PLAN_TEMPLATE)
    _write(tmp_path, "templates/week-review.md", REVIEW_TEMPLATE)
    _write(tmp_path, "templates/week-log.md", LOG_TEMPLATE)
    _write(tmp_path, "terms/2026-fall/README.md", "# 2026 Fall\n")
    _write(tmp_path, f"{OLD}/plan.md", OLD_PLAN)
    _write(tmp_path, f"{OLD}/review.md", REVIEW_TEMPLATE.replace("<date>", "x"))
    return tmp_path


def _files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_carries_open_todos_and_overdue_but_not_ticked_ones(life):
    result = roll_over(life, date(2026, 11, 9))  # the new Monday
    plan = (life / NEW / "plan.md").read_text(encoding="utf-8")
    assert result.carried == 6 and result.overdue == 3
    assert "<date>" not in plan and plan.startswith(
        "# Week plan (Mon 2026-11-09 to Sun 2026-11-15)"
    )
    assert "Lab 5" not in plan and "A29" not in plan  # ticked stays behind, never re-opened
    overdue = plan.split("## Overdue\n")[1].split("\n\n")[0].splitlines()
    assert overdue == [
        # Already carried: the old mark stays, never a second one.
        "- [ ] [hist-205] Memo (was due 2026-10-26 08:30; carried; late)",
        "- [ ] [hist-205] Lab 2 (was due 2026-10-14; carried from 10-12)",
        # Due before the new Monday: late, so it moves to Overdue as "was due".
        "- [ ] [chem-120] A30 Titration (was due 2026-11-04; posted 2026-11-02; carried from 11-02)"
        " (mail)",
    ]
    assert (
        "## CHEM 120\n- [ ] [chem-120] fill from the course site\n"
        # Regression: a sub-line's past date doesn't make its parent late.
        "- [ ] [chem-120] Lab 8 (due 2026-11-12 10:00; carried from 11-02) (site)\n"
        "  - pre-lab first (due 2026-11-01)\n"
        # Regression: an impossible date is no due date, not a crash.
        "- [ ] [chem-120] Typo date (due 2026-02-30; carried from 11-02)\n"
    ) in plan
    # The template's own placeholder isn't doubled; a section the template lacks is kept.
    assert plan.count("fill from backlog") == 1
    assert plan.endswith(
        "## Errands\n- [ ] [errands] Pick up the package (carried from 11-02) (mail)\n"
    )
    review = (life / OLD / "review.md").read_text(encoding="utf-8")
    assert "- 2 todo(s) ticked in plan.md:\n  - [chem-120] Lab 5" in review
    assert f"- 6 open todo(s) moved to {NEW}/plan.md" in review
    # Only Lab 2 has a dated mark 3+ weeks old; a plain "carried" has no age.
    assert "weeks:\n  - [hist-205] Lab 2 (was due 2026-10-14; carried from 10-12)\n" in review
    assert (life / NEW / "workspace" / "README.md").is_file()
    log = (life / NEW / "log.md").read_text(encoding="utf-8")
    assert log == (
        "# Week log (Mon 2026-11-09 to Sun 2026-11-15)\n\n## Mon 2026-11-09\n\n## Sun 2026-11-15\n"
    )


def test_dry_run_writes_nothing_and_a_second_run_does_nothing(life):
    _write(life, f"{NEW}/workspace/notes.md", "mine")  # scratch saved before the rollover
    _write(life, f"{NEW}/log.md", "partial")  # a run that crashed before writing the plan
    before = _files(life)
    assert roll_over(life, date(2026, 11, 13), dry_run=True).writes
    assert _files(life) == before
    assert roll_over(life, date(2026, 11, 13)).status == "rolled"  # the crashed run resumes
    after_first = _files(life)
    assert after_first[f"{NEW}/workspace/notes.md"] == b"mine"
    assert after_first[f"{NEW}/log.md"] == b"partial"
    assert f"{NEW}/plan.md" in after_first
    assert roll_over(life, date(2026, 11, 14)).status == "current"
    assert _files(life) == after_first


def test_catch_up_jumps_to_this_week_and_carries_everything(life):
    # Regression: lateness is judged on the rollover's day, so a Wednesday rollover
    # moves a todo due that Monday to Overdue (else it's never announced).
    _write(life, f"{OLD}/plan.md", OLD_PLAN + "- [ ] [errands] Form (due 2026-11-23)\n")
    result = roll_over(life, date(2026, 11, 25))  # a Wednesday, 3 weeks after the last plan
    weeks = sorted(p.name for p in (life / "terms/2026-fall/weeks").iterdir())
    assert weeks == ["2026-11-02-to-11-08", "2026-11-23-to-11-29"]
    assert result.carried == 7 and result.overdue == 5  # Lab 8 and Form are late by now
    plan = (life / "terms/2026-fall/weeks/2026-11-23-to-11-29/plan.md").read_text(encoding="utf-8")
    assert "Lab 8 (was due 2026-11-12 10:00; carried from 11-02) (site)" in plan
    assert "- [ ] [errands] Form (was due 2026-11-23; carried from 11-02)" in plan


def test_an_early_plan_gets_the_missing_todos_merged_in_once(life):
    early = (
        "# Week plan (Mon 2026-11-09 to Sun 2026-11-15)\n\n## CHEM 120\n"
        "- [x] [chem-120] Lab 8 (due 2026-11-12 10:00) (site)\n- [ ] [chem-120] New thing\n"
    )
    _write(life, f"{NEW}/plan.md", early)  # made by hand on the Sunday
    result = roll_over(life, date(2026, 11, 9))
    assert (result.status, result.carried) == ("merged", 5)  # only what was added (not Lab 8)
    plan = (life / NEW / "plan.md").read_text(encoding="utf-8")
    # The early plan had no Overdue: it's added as the first section.
    assert plan.index("## Overdue") < plan.index("## CHEM 120")
    # The owner's lines stay; a todo they ticked isn't re-opened; the rest is added once.
    assert (
        "- [x] [chem-120] Lab 8 (due 2026-11-12 10:00) (site)\n- [ ] [chem-120] New thing\n" in plan
    )
    assert "[ ] [chem-120] Lab 8" not in plan
    assert plan.count("Pick up the package") == 1 and "Typo date" in plan
    assert '"carried" = moved over from the 2026-11-02 week' in plan
    merged = _files(life)
    assert roll_over(life, date(2026, 11, 10)).status == "current"
    assert _files(life) == merged


@pytest.mark.parametrize(
    ("other_term_readme", "status", "term"),
    [
        (None, "between-terms", None),  # fall ended, no next term: stop, write nothing
        ("Term dates: 2027-01-04 to 2027-05-07\n", "between-terms", None),  # not started yet
        ("Term dates: 2026-12-28 to 2027-05-07\n", "rolled", "2027-spring"),
    ],
)
def test_term_boundary(life, other_term_readme, status, term):
    _write(life, "terms/2026-fall/README.md", "# Fall\nTerm dates: 2026-08-24 to 2026-12-18\n")
    if other_term_readme:
        _write(life, "terms/2027-spring/README.md", other_term_readme)
    before = _files(life)
    result = roll_over(life, date(2026, 12, 29))
    assert result.status == status
    if term is None:
        assert _files(life) == before
    else:
        assert (life / f"terms/{term}/weeks/2026-12-28-to-01-03/plan.md").is_file()


FALL = "Term dates: 2026-08-24 to 2026-12-18\n"
SPRING = "Term dates: 2026-01-05 to 2026-05-08\n"
INBOX = {"inbox.md": "# Inbox\n"}


@pytest.mark.parametrize(
    ("files", "status", "term"),
    [
        ({}, "no-source", None),  # no inbox.md: life/ isn't used, so nothing is written
        (INBOX, "started", "2026"),  # no terms yet: terms/2026/ is created
        (
            {**INBOX, "terms/fall/README.md": FALL, "terms/other/README.md": "# x\n"},
            "started",
            "fall",
        ),  # the covering term among several
        ({**INBOX, "terms/spring/README.md": SPRING}, "between-terms", None),  # it has ended
    ],
)
def test_first_week(tmp_path, files, status, term):
    for relative, text in files.items():
        _write(tmp_path, relative, text)
    before = _files(tmp_path)
    assert roll_over(tmp_path, date(2026, 11, 11)).status == status
    if term is None:
        assert _files(tmp_path) == before
        return
    plan = tmp_path / f"terms/{term}/weeks/2026-11-09-to-11-15/plan.md"
    assert plan.read_text(encoding="utf-8").startswith("# Week plan (Mon 2026-11-09 to Sun")
    assert (tmp_path / f"terms/{term}/README.md").is_file()
    started = _files(tmp_path)
    assert roll_over(tmp_path, date(2026, 11, 12)).status == "current"
    assert _files(tmp_path) == started
