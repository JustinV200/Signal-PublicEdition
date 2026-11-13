"""Tests for tasks.json writes: the field checks, partial updates and pruning of done tasks."""

from datetime import datetime, timedelta

import pytest

from signal_tasks import (
    DONE_KEEP_MAX,
    TaskChange,
    TaskError,
    group_tasks,
    mark_done,
    read_tasks,
    set_task,
)

NOW = datetime(2026, 10, 20, 12, 0).astimezone()


@pytest.mark.parametrize(
    ("task_id", "change"),
    [
        ("brief-p2", TaskChange(name="Brief", pct=101)),
        ("brief-p2", TaskChange(name="Brief", pct=-1)),
        ("brief-p2", TaskChange(name="Brief", status="stuck")),
        ("Brief P2", TaskChange(name="Brief")),
        ("brief-p2", TaskChange(name="Brief", status="needs_you")),
        ("brief-p2", TaskChange(name="two\nlines")),
        ("brief-p2", TaskChange(pct=10)),  # a new task needs a name
    ],
)
def test_set_refuses_a_bad_field_and_writes_nothing(tmp_path, task_id, change) -> None:
    path = tmp_path / "tasks.json"
    with pytest.raises(TaskError):
        set_task(path, task_id, change, NOW)
    assert not path.exists()


def test_set_updates_only_the_given_fields_and_clears_you_on_leaving_needs_you(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    set_task(path, "a", TaskChange(name="A", status="needs_you", you="approve", next="x"), NOW)
    task = set_task(path, "a", TaskChange(pct=40, status="building"), NOW)
    assert (task.name, task.pct, task.status, task.next, task.you) == ("A", 40, "building", "x", "")
    assert [t.id for t in read_tasks(path).tasks] == ["a"]


def test_done_tasks_are_pruned_after_a_day_and_past_the_newest_twenty(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    set_task(path, "old", TaskChange(name="Old"), NOW - timedelta(hours=30))
    mark_done(path, "old", NOW - timedelta(hours=30))
    for index in range(DONE_KEEP_MAX + 1):
        at = NOW - timedelta(minutes=DONE_KEEP_MAX + 1 - index)
        set_task(path, f"t{index}", TaskChange(name=f"T{index}"), at)
        mark_done(path, f"t{index}", at)
    set_task(path, "live", TaskChange(name="Live", pct=5, status="building"), NOW)
    ids = {task.id for task in read_tasks(path).tasks}
    assert "old" not in ids and "t0" not in ids  # too old, and the 21st newest
    assert {"t1", f"t{DONE_KEEP_MAX}", "live"} <= ids
    assert len(ids) == DONE_KEEP_MAX + 1


def test_groups_put_active_by_pct_then_queued_then_done(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    set_task(path, "q", TaskChange(name="Q"), NOW)
    set_task(path, "lo", TaskChange(name="Lo", pct=20, status="review"), NOW)
    set_task(path, "hi", TaskChange(name="Hi", pct=80, status="needs_you", you="ok it"), NOW)
    set_task(path, "d", TaskChange(name="D"), NOW)
    mark_done(path, "d", NOW)
    groups = group_tasks(read_tasks(path).tasks)
    assert [t.id for t in groups.active] == ["hi", "lo"]
    assert ([t.id for t in groups.queued], [t.id for t in groups.done]) == (["q"], ["d"])
    assert (groups.needs_you, groups.overall_pct) == (1, 33)
