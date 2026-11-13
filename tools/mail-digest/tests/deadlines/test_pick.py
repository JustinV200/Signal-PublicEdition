"""Tests for mail_digest.deadlines: which plan todos are announced now, and their keys."""

from datetime import datetime, timedelta, timezone

import pytest

from mail_digest.deadlines import pick_announcements, select_announcements

# Monday 07:00, as the scheduled run sees it.
NOW = datetime(2026, 10, 19, 7, 0, tzinfo=timezone(timedelta(hours=-4)))
COURSE = "## CHEM 120"
OVERDUE = "## Overdue"


@pytest.mark.parametrize(
    ("heading", "todo", "expected"),
    [
        # No time means the end of that day.
        (
            COURSE,
            "- [ ] [chem-120] A24 Graphs (due 2026-10-19, time TODO: verify) (mail)",
            (
                "due|2026-10-19|chem-120-a24-graphs",
                "CHEM 120, due today by end of day: A24 Graphs.",
            ),
        ),
        # Notes cut out leave no stray space before the punctuation.
        (
            COURSE,
            "- [ ] [chem-120] Lab 3 (tree.c, Makefile), push it (due 2026-10-19 10:00) (site)",
            (
                "due|2026-10-19|chem-120-lab-3-push-it",
                "CHEM 120, due today at 10:00: Lab 3, push it.",
            ),
        ),
        # Tomorrow counts only within 24 hours of now.
        (
            COURSE,
            "- [ ] [hist-205] Notebook (due 2026-10-20 06:30; moved from Mon)",
            ("due|2026-10-20|hist-205-notebook", "HIST 205, due tomorrow at 06:30: Notebook."),
        ),
        (COURSE, "- [ ] [hist-205] Notebook (due 2026-10-20 08:30)", None),
        (COURSE, "- [ ] [hist-205] Notebook (due 2026-10-20)", None),
        # Past its time but not moved under Overdue: not announced as due.
        (COURSE, "- [ ] [chem-120] A19 (due 2026-10-19 06:59)", None),
        (
            OVERDUE,
            "- [ ] [hist-205] Practice Quiz (was due 2026-10-15 17:00; late) (mail)",
            ("overdue|hist-205-practice-quiz", "HIST 205, overdue: Practice Quiz."),
        ),
        # Already done.
        (COURSE, "- [x] [chem-120] A20 (due 2026-10-19 23:59)", None),
        (OVERDUE, "- [x] [hist-205] Practice Quiz (was due 2026-10-15 17:00)", None),
    ],
)
def test_select_picks_due_soon_and_overdue_open_todos(heading, todo, expected):
    picks = select_announcements(f"# Week plan\n\n{heading}\n{todo}\n", NOW)
    assert [(pick.key, pick.sentence) for pick in picks] == ([expected] if expected else [])


@pytest.mark.parametrize(
    ("weeks", "now"),
    [
        # Sunday night: next week's plan exists too and repeats the todo; spoken once.
        (("2026-10-19-to-10-25", "2026-10-26-to-11-01"), NOW + timedelta(days=6, hours=15)),
        # Monday morning before the owner's rollover: last week's plan stands in.
        (("2026-10-19-to-10-25",), NOW + timedelta(days=7)),
    ],
    ids=["sunday", "monday-before-rollover"],
)
def test_picks_a_monday_todo_from_whichever_plans_exist(tmp_path, weeks, now):
    todo = "- [ ] [hist-205] 6. Project Demo (due 2026-10-26 08:30) (mail)\n"
    for week in weeks:
        folder = tmp_path / "terms" / "2026-fall" / "weeks" / week
        folder.mkdir(parents=True)
        (folder / "plan.md").write_text(f"# Week plan\n{COURSE}\n{todo}", encoding="utf-8")
    keys = [pick.key for pick in pick_announcements(tmp_path, now)]
    assert keys == ["due|2026-10-26|hist-205-6-project-demo"]
