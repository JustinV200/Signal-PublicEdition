"""The task grid: the layout's slot rules, and items that say each status in a number and words."""

from datetime import datetime, timedelta

import pytest
from signal_tasks import Task, UsageSummary, group_tasks

from whiteboard.display.scene import item_from_dict
from whiteboard.tasks_grid import grid_items, plan_grid, scale_items

NOW = datetime(2026, 10, 20, 12, 0).astimezone()


@pytest.mark.parametrize(
    ("active", "box_width", "queued_width", "hidden"),
    [(2, 340, 340, 0), (7, 340, 340, 0), (8, 255, 524, 0), (10, 255, 255, 0), (12, 255, 255, 2)],
)
def test_plan_puts_queued_and_done_in_the_last_slots(active, box_width, queued_width, hidden):
    plan = plan_grid(active)
    assert len(plan.active) == active - hidden and plan.hidden == hidden
    assert plan.active[0].w == box_width and plan.queued.w == queued_width
    assert plan.done.x > plan.queued.x and plan.done.y == plan.queued.y
    # Queued and done come after every active box in reading order.
    last = plan.active[-1]
    assert (plan.queued.y, plan.queued.x) > (last.y, last.x)


def _task(task_id: str, pct: int, status: str, you: str = "") -> Task:
    return Task(task_id, task_id.upper(), pct, status, "next step", you, NOW.isoformat())


def test_items_are_valid_and_carry_numbers_words_and_you():
    tasks = [
        _task("a", 80, "review"),
        _task("b", 40, "needs_you", "approve it"),
        _task("q", 0, "queued"),
    ]
    usage = UsageSummary(None, None, 3, NOW - timedelta(minutes=2))
    items = scale_items(grid_items(group_tasks(tasks), usage, NOW), 1114, 720)
    for item in items:
        item_from_dict(item)  # the daemon's own checks
    by_id = {item["id"]: item for item in items}
    assert by_id["t-b"]["content"].splitlines()[:3] == ["B  40%", "needs you", "YOU: approve it"]
    assert "<text" not in by_id["t-a"]["content"]
    assert by_id["nums"]["content"].count("<text") == 4  # 2 active + queued + done
    assert ">1</text>" in by_id["nums"]["content"] and ">3</text>" in by_id["nums"]["content"]
    assert by_id["header"]["content"].startswith("Signal main session: 2 active")
    assert "1 review 2 building 3 NEEDS YOU" in by_id["header"]["content"]
    assert by_id["queued"]["content"].splitlines()[0] == "Queued: 1 task, none started"
    assert by_id["usage"]["content"] == "5h: --   Week: --\nAgents: 3, 2 min ago"
