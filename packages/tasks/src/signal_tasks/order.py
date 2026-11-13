"""The display order the console's Tasks page and the whiteboard grid share, plus header sums.

Active tasks (review, building, needs_you) come first, most finished first,
then the queued ones, then the done ones, newest first. That's the
whiteboard-task-grid rule: the most finished at top-left, queued and done last.
"""

from dataclasses import dataclass

from signal_tasks.model import Task


@dataclass(frozen=True)
class TaskGroups:
    """The tasks split the way every display shows them.

    Attributes:
        active: review, building and needs_you tasks, by pct (highest first).
        queued: Not started, in file order.
        done: Finished, newest first.
    """

    active: tuple[Task, ...]
    queued: tuple[Task, ...]
    done: tuple[Task, ...]

    @property
    def needs_you(self) -> int:
        """How many active tasks wait on the owner."""
        return sum(1 for task in self.active if task.status == "needs_you")

    @property
    def overall_pct(self) -> int | None:
        """The mean pct over active and queued tasks (rounded), or None with none."""
        open_tasks = (*self.active, *self.queued)
        if not open_tasks:
            return None
        return round(sum(task.pct for task in open_tasks) / len(open_tasks))


def group_tasks(tasks: tuple[Task, ...] | list[Task]) -> TaskGroups:
    """Split and sort `tasks` for display (stable: ties keep file order)."""
    active = [task for task in tasks if task.status not in ("queued", "done")]
    active.sort(key=lambda task: task.pct, reverse=True)
    queued = [task for task in tasks if task.status == "queued"]
    done = sorted(
        (task for task in tasks if task.status == "done"),
        key=lambda task: task.updated_at,
        reverse=True,
    )
    return TaskGroups(tuple(active), tuple(queued), tuple(done))
