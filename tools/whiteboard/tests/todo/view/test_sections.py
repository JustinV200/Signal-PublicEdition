"""build_groups: the 7-day window, Overdue folding, of note, sorting, hiding and duplicate lines."""

from datetime import date
from pathlib import Path

from whiteboard.todo.source import parse_plan
from whiteboard.todo.view import build_groups

TODAY = date(2026, 10, 19)


def groups_for(text: str, today: date = TODAY, hidden: frozenset[str] = frozenset()):
    entries = parse_plan(text, Path("plan.md"), date(2026, 10, 19))
    return [
        (group.label, [(row.entry.text, row.due_label) for row in group.rows])
        for group in build_groups(entries, today, hidden)
    ]


def test_the_week_plan_groups_into_overdue_today_tomorrow_week_and_of_note(
    week_plan_text: str,
) -> None:
    assert groups_for(week_plan_text) == [
        # The undated A15 is folded into the heading.
        ("Overdue · +1 older", [("Practice Quiz", "4d late")]),
        ("Today · Mon 19 Oct", [("A19 Recursion Drill", "23:59")]),
        ("Tomorrow · Tue 20 Oct", [("A17 Queues", "")]),
        # An of-note item due inside the window shows on its day.
        ("This week", [("Study group", "Wed 15:00"), ("Reading video", "Fri 12:00")]),
        # Undated and later of-note items; the undated one last. "Midterm exam" (later, not
        # of note) and "Check grades" (undated, not of note) aren't shown.
        ("Work items of note", [("Poster draft", "Fri 6 Nov"), ("Pitch deck draft", "")]),
    ]


def test_the_window_runs_from_today_to_seven_days_ahead() -> None:
    plan = "\n".join(
        f"- [ ] [x] Day {offset} (due 2026-10-{19 + offset:02d})" for offset in (-1, 0, 7, 8)
    )
    # Past due outside ## Overdue: an open item is still overdue, a done one isn't shown.
    plan += "\n- [x] [x] Done late (due 2026-10-17)"
    groups = groups_for(plan)
    assert groups[0] == ("Overdue", [("Day -1", "1d late")])
    shown = [text for _, rows in groups[1:] for text, _ in rows]
    assert shown == ["Day 0", "Day 7"]


def test_items_sort_by_time_untimed_last_and_hidden_ones_are_left_out() -> None:
    plan = (
        "- [ ] [a] Late (due 2026-10-20 18:00)\n"
        "- [ ] [a] Whenever (due 2026-10-20)\n"
        "- [ ] [a] Early (due 2026-10-20 08:00)\n"
        "- [x] [a] Gone (due 2026-10-20 09:00)\n"
    )
    entries = parse_plan(plan, Path("plan.md"), TODAY)
    hidden = frozenset({entries[3].id})
    assert groups_for(plan, hidden=hidden) == [
        ("Tomorrow · Tue 20 Oct", [("Early", "08:00"), ("Late", "18:00"), ("Whenever", "")])
    ]


def test_overdue_shows_recent_items_newest_first_and_folds_the_rest() -> None:
    # Open items 1 to 6 and 9 days late, one done today in the Overdue section, and one
    # filed under Overdue but re-dated to today.
    plan = "## Overdue\n- [x] [a] Done today (was due 2026-10-18)\n"
    plan += "- [ ] [a] Moved to today (due 2026-10-19)\n" + "\n".join(
        f"- [ ] [a] Late {days} (due 2026-10-{19 - days:02d})" for days in (1, 2, 3, 4, 5, 6, 9)
    )
    (label, rows), today = groups_for(plan)[:2]
    # The re-dated line shows on its day, not as "0d late".
    assert today == ("Today · Mon 19 Oct", [("Moved to today", "")])
    # Five rows at most, all within the last 7 days: 6 days late is past the cap, 9 too old.
    assert label == "Overdue · +2 older"
    assert [text for text, _ in rows] == [
        "Late 1",
        "Late 2",
        "Late 3",
        "Late 4",
        "Late 5",
        "Done today",
    ]


def test_a_carried_item_counts_once_with_the_later_plans_line() -> None:
    # Sunday, after next week's plan was made: the essay is in both plans.
    sunday = date(2026, 10, 25)
    this_plan, next_plan = Path("2026-10-19-to-10-25/plan.md"), Path("2026-10-26-to-11-01/plan.md")
    this_week = parse_plan("- [ ] [a] Essay (due 2026-10-29)", this_plan, TODAY)
    next_week = parse_plan("- [x] [a] Essay (due Thu)", next_plan, date(2026, 10, 26))
    groups = build_groups([*this_week, *next_week], sunday)
    rows = [row.entry for group in groups for row in group.rows]
    assert len(rows) == 1 and rows[0].source.path == next_plan
