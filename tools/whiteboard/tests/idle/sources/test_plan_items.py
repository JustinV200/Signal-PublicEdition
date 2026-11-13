"""TODAY, PRIORITIES and the plan side of UPCOMING, from the shared fixture plan (conftest)."""

from datetime import date, timedelta
from pathlib import Path

from whiteboard.idle import (
    overdue_count,
    read_priorities,
    today_rows,
    upcoming_items,
    upcoming_rows,
)
from whiteboard.todo import DoneTracking, build_groups, read_week_entries, track

TUESDAY = date(2026, 10, 20)
MONDAY = date(2026, 10, 19)
LABELS = {"chem-120": "CHEM 120"}


def test_today_lists_overdue_then_today_then_fills_with_later_open_items(life_dir: Path) -> None:
    entries, _ = read_week_entries(life_dir, TUESDAY)
    # A17 (due today) was ticked today, so it stays, struck through.
    result = track(entries, DoneTracking(), TUESDAY)
    rows = today_rows(
        build_groups(entries, TUESDAY, result.hidden_ids), TUESDAY, result.done_ids, LABELS
    )
    shown = [(row["text"], row["due"], row["when"], row["done"]) for row in rows]
    assert shown == [
        # Due yesterday in a day section: overdue all the same. Newest first; the
        # undated A15 is folded away but still counted.
        ("A19 Recursion Drill", "1d late", "overdue", False),
        ("Practice Quiz", "5d late", "overdue", False),
        ("A17 Queues", "✓ done", "today", True),
        ("Study group", "Wed", "later", False),
        ("Reading video", "Fri", "later", False),
    ]
    groups = build_groups(entries, TUESDAY, result.hidden_ids)
    assert overdue_count(groups, result.done_ids) == 3
    # Tags without a configured label are title-cased.
    assert [rows[1]["chip"]["label"], rows[3]["chip"]["label"]] == ["Hist 205", "Side Project"]
    # Ticked before today: hidden (the TODO view's tracking).
    a17 = next(entry.id for entry in entries if entry.text == "A17 Queues")
    earlier = track(entries, DoneTracking({a17: MONDAY}), TUESDAY)
    rows = today_rows(
        build_groups(entries, TUESDAY, earlier.hidden_ids), TUESDAY, earlier.done_ids, LABELS
    )
    assert "A17 Queues" not in [row["text"] for row in rows]


def test_upcoming_is_open_dated_items_after_today_soonest_first(life_dir: Path) -> None:
    entries, _ = read_week_entries(life_dir, TUESDAY)
    items = upcoming_items(entries, TUESDAY, TUESDAY + timedelta(days=7), LABELS)
    rows = upcoming_rows(items, TUESDAY)
    # A19 was due Monday (past), A17 is today and done, the midterm exam is out of the window.
    assert [(row["day"], row["text"]) for row in rows] == [
        ("Wed", "Study group 15:00"),
        ("Fri", "Reading video 12:00"),
    ]


def test_priorities_skip_past_due_and_all_done_lines_and_cap_at_three() -> None:
    plan = """# Week
## Priorities
1. [chem-120] A19 first (due 2026-10-19 23:59).
2. [chem-120] A22 (due 2026-10-19 23:59), then Reading (due 2026-10-23 23:59).
3. [school] ~~Renew library card~~ done 2026-10-19 (mail).
3. No date at all.
4. [hist-205] Notebook (due Wed 08:30)
5. Fifth, never shown.
## CHEM 120
6. Not a priority.
"""
    rows = read_priorities(plan, MONDAY, TUESDAY, LABELS)
    assert [(row["chip"] and row["chip"]["label"], row["text"]) for row in rows] == [
        ("CHEM 120", "A22, then Reading"),
        (None, "No date at all"),
        ("Hist 205", "Notebook"),
    ]
