"""parse_plan and the week lookup: sections, tags, done marks, stable ids, which plans are read."""

from datetime import date
from pathlib import Path

import pytest

from whiteboard.todo.source import (
    SECTION_OF_NOTE,
    SECTION_OTHER,
    SECTION_OVERDUE,
    Due,
    parse_plan,
    read_week_entries,
    week_folder_name,
)

MONDAY = date(2026, 10, 19)


@pytest.mark.parametrize(
    ("day", "folder"),
    [
        (date(2026, 10, 19), "2026-10-19-to-10-25"),  # Monday
        (date(2026, 10, 25), "2026-10-19-to-10-25"),  # Sunday, same week
        (date(2027, 1, 1), "2026-12-28-to-01-03"),  # across New Year: the Monday's year
    ],
)
def test_week_folder_name_is_the_monday_to_sunday_range(day: date, folder: str) -> None:
    assert week_folder_name(day) == folder


def test_parse_plan_reads_todo_lines_with_their_sections(week_plan_text: str) -> None:
    entries = parse_plan(week_plan_text, Path("plan.md"), MONDAY)
    by_text = {entry.text: entry for entry in entries}
    # The numbered Priorities line is not a todo.
    assert len(entries) == 10 and "A19 first" not in by_text
    assert by_text["Practice Quiz"].section == SECTION_OVERDUE
    assert by_text["A19 Recursion Drill"].section == SECTION_OTHER
    assert by_text["A19 Recursion Drill"].tag == "chem-120"
    assert by_text["A17 Queues"].is_done and not by_text["A19 Recursion Drill"].is_done
    # "### Later" stays inside "## CHEM 120"; "## Of note" starts the of-note section.
    assert by_text["Midterm exam"].section == SECTION_OTHER
    assert by_text["Pitch deck draft"].section == SECTION_OF_NOTE
    assert by_text["Reading video"].due == Due(date(2026, 10, 23), "12:00")
    source = by_text["A19 Recursion Drill"].source
    assert week_plan_text.splitlines()[source.line_no] == source.text


def test_item_id_survives_ticking_the_box_and_editing_the_due_note() -> None:
    open_line = "- [ ] [chem-120] A19 Recursion Drill (due 2026-10-19 23:59)"
    done_line = "- [x] [chem-120] A19  Recursion drill (due 2026-10-20; submitted)"
    first = parse_plan(open_line, Path("plan.md"), MONDAY)[0]
    second = parse_plan(done_line, Path("plan.md"), MONDAY)[0]
    assert first.id == second.id
    assert parse_plan("- [ ] [club] A19 Recursion Drill", Path("plan.md"), MONDAY)[0].id != first.id


def test_this_and_next_weeks_plans_are_read_in_order(life_dir: Path, write_week_plan) -> None:
    # Next week's "Thu" is resolved against next week's Monday, not this one's.
    write_week_plan("2026-10-26-to-11-01", "## CHEM 120\n- [ ] [chem-120] Quiz (due Thu)\n")
    write_week_plan("2026-11-02-to-11-08", "- [ ] [chem-120] Too far (due Thu)\n")
    entries, plans = read_week_entries(life_dir, date(2026, 10, 25))
    assert [plan.week for plan in plans] == ["2026-10-19-to-10-25", "2026-10-26-to-11-01"]
    assert entries[-1].text == "Quiz" and entries[-1].due == Due(date(2026, 10, 29))


def test_a_recurring_item_gets_one_id_per_due_day(life_dir: Path, write_week_plan) -> None:
    write_week_plan(
        "2026-10-19-to-10-25",
        "## Overdue\n- [ ] [chem-120] Reading (due Tue)\n"
        "## CHEM 120\n- [ ] [chem-120] Reading (due Tue)\n- [ ] [chem-120] Reading (due Thu)\n"
        "- [ ] [chem-120] Reading\n",
    )
    (overdue, tue, thu, undated), _ = read_week_entries(life_dir, MONDAY)
    # The Overdue copy dated Tue ticks with Tue's line; the undated one keeps the plain id.
    assert overdue.id == tue.id != thu.id
    plain_id = parse_plan("- [ ] [chem-120] Reading", Path("plan.md"), MONDAY)[0].id
    assert undated.id == plain_id and plain_id not in {tue.id, thu.id}
