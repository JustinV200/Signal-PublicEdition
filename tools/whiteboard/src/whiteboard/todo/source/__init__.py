"""Public API of whiteboard.todo.source: read todo lines from life/, and tick one back.

Reading: find this and next week's plan.md, parse their todo lines and due dates.
Writing: set_line_done flips one exact checkbox and is the only write to life/.
"""

from whiteboard.todo.source.due import Due, parse_due_spec, split_due
from whiteboard.todo.source.lookup import TodoLookupError, find_entries
from whiteboard.todo.source.plan_edit import PlanEditError, set_line_done
from whiteboard.todo.source.plan_file import PLAN_FILE, PlanText, read_plan
from whiteboard.todo.source.plan_lines import (
    SECTION_OF_NOTE,
    SECTION_OTHER,
    SECTION_OVERDUE,
    PlanEntry,
    SourceLine,
    item_id,
    parse_plan,
)
from whiteboard.todo.source.weeks import (
    WeekPlan,
    find_week_plans,
    read_week_entries,
    week_folder_name,
)

__all__ = [
    "PLAN_FILE",
    "SECTION_OF_NOTE",
    "SECTION_OTHER",
    "SECTION_OVERDUE",
    "Due",
    "PlanEditError",
    "PlanEntry",
    "PlanText",
    "SourceLine",
    "TodoLookupError",
    "WeekPlan",
    "find_entries",
    "find_week_plans",
    "item_id",
    "parse_due_spec",
    "parse_plan",
    "read_plan",
    "read_week_entries",
    "set_line_done",
    "split_due",
    "week_folder_name",
]
