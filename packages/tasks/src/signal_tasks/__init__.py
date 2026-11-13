"""Public API of signal_tasks: the orchestrator's task list, its checks, pruning and display order.

The console's `console tasks` CLI writes it; the console's Tasks page and the
whiteboard's task grid read it, with the usage line from tools/usage.
"""

from signal_jsonstate import StateFileError

from signal_tasks.model import (
    STATUS_NUMBERS,
    STATUS_WORDS,
    Task,
    TaskError,
    check_task,
    task_to_dict,
)
from signal_tasks.order import TaskGroups, group_tasks
from signal_tasks.prune import DONE_KEEP_FOR, DONE_KEEP_MAX, prune
from signal_tasks.store import TaskChange, TaskList, mark_done, read_tasks, remove_task, set_task
from signal_tasks.usage import NO_USAGE, UsageSummary, UsageWindow, read_usage

__all__ = [
    "DONE_KEEP_FOR",
    "DONE_KEEP_MAX",
    "NO_USAGE",
    "STATUS_NUMBERS",
    "STATUS_WORDS",
    "StateFileError",
    "Task",
    "TaskChange",
    "TaskError",
    "TaskGroups",
    "TaskList",
    "UsageSummary",
    "UsageWindow",
    "check_task",
    "group_tasks",
    "mark_done",
    "prune",
    "read_tasks",
    "read_usage",
    "remove_task",
    "set_task",
    "task_to_dict",
]
