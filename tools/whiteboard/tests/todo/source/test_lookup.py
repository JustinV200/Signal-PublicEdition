"""find_entries: an id, or a piece of text only one item has, names exactly one item."""

from datetime import date
from pathlib import Path

import pytest

from whiteboard.todo.source import TodoLookupError, find_entries, parse_plan

PLAN = "## CHEM 120\n- [ ] [chem-120] A19 (due 2026-10-19 23:59)\n- [ ] [chem-120] A22\n"


def test_lookup_needs_one_item() -> None:
    entries = parse_plan(PLAN, Path("plan.md"), date(2026, 10, 19))
    assert find_entries(entries, entries[0].id) == [entries[0]]
    with pytest.raises(TodoLookupError, match="2 todo items"):
        find_entries(entries, "chem-120")
    with pytest.raises(TodoLookupError, match="no todo item"):
        find_entries(entries, "A99")
