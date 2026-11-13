"""assignment_check.writer.budget: the writer never gets more than 4 line changes a check."""

from mail_digest.assignment_check.findings import Item
from mail_digest.assignment_check.writer import open_lines, select_items

PLAN = """# Week plan

## Overdue
- [ ] [hist-205] Practice Quiz (was due 2026-10-15 17:00)
- [ ] [chem-120] A18 (was due 2026-10-16; TODO: verify it was handed in)

## CHEM 120
- [ ] [chem-120] A14 (TODO: verify it was handed in)
- [ ] [chem-120] A15 (TODO: verify it was handed in)
- [ ] [chem-120] A18 handed in?
- [ ] [chem-120] A19 Recursion Drill (due 2026-10-19 23:59)
- [x] [chem-120] A08 (turned in per Classroom 2026-10-20) (site)
"""


def _item(name, course="chem-120", status="open", overdue=False):
    return Item(course, "classroom", name, "assignment", "", status, "https://x", overdue)


def test_changes_stay_within_the_budget_and_the_rest_wait():
    items = (
        _item("A08 Pipes", status="done"),  # already ticked: nothing to do
        _item("A14 Linked Lists", status="done"),  # 1 line
        _item("A15 Stacks", status="done"),  # 1 line
        _item("A18 Sorting", status="done"),  # 2 lines (Overdue and the section)
        _item("A19 Recursion Drill", overdue=True),  # 1 line, moves under Overdue first
        _item("Practice Quiz", course="hist-205", overdue=True),  # already there
        _item("A22 Hashing"),  # new: an add
    )
    selection = select_items(items, open_lines({"plan.md": PLAN}))
    # Overdue first: A19 (1), then A14 (1), A15 (1); A18 (2) would make 5, so it waits.
    assert [i.name for i in selection.changes] == [
        "A19 Recursion Drill",
        "A14 Linked Lists",
        "A15 Stacks",
    ]
    assert [i.name for i in selection.adds] == ["A22 Hashing"]
    assert selection.spilled == 1
