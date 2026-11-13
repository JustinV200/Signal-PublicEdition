"""Due notes in todo text: the formats in use, weekday resolution, and unreadable dates."""

from datetime import date

import pytest

from whiteboard.todo.source import Due, split_due

MONDAY = date(2026, 10, 19)


@pytest.mark.parametrize(
    ("text", "due", "shown"),
    [
        ("A19 (due 2026-10-19 23:59)", Due(date(2026, 10, 19), "23:59"), "A19"),
        ("Midterm exam (due 2026-10-30; slot booked)", Due(date(2026, 10, 30)), "Midterm exam"),
        ("HW (was due 2026-10-15 17:00; upload late)", Due(date(2026, 10, 15), "17:00"), "HW"),
        ("A01, A02 (were due 2026-08-27, 2026-08-31; unknown)", Due(date(2026, 8, 27)), "A01, A02"),
        # Weekdays are days of the plan's own week, shortened or not, with an optional time.
        ("Video (due Thu)", Due(date(2026, 10, 22)), "Video"),
        ("Video (due thursday 8:05)", Due(date(2026, 10, 22), "08:05"), "Video"),
        ("Talk (due Sun 25:00)", Due(date(2026, 10, 25)), "Talk"),
        # Unreadable dates give no due date, but the note still leaves the shown text.
        ("A15 (due date TODO: verify; no mark)", None, "A15"),
        ("A07 (due 2026-11-04); feedback 10-26", Due(date(2026, 11, 4)), "A07; feedback 10-26"),
        ("Group project (project due 2026-12-08)", None, "Group project (project due 2026-12-08)"),
    ],
)
def test_split_due_reads_the_formats_in_use(text: str, due: Due | None, shown: str) -> None:
    assert split_due(text, MONDAY) == (due, shown)
