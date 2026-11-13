"""Read and change tasks.json: upsert, mark done, remove, all under one lock.

The path is the caller's (the console passes tools/console/.state/tasks.json);
its lock is `<path>.lock` beside it. Writes go through signal_jsonstate, so a
reader only ever sees a whole file and needs no lock. Every write prunes old
done tasks (prune.py) and stamps the file's `updated_at`.
"""

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from signal_jsonstate import read_json_object, state_lock, write_json_atomic

from signal_tasks.model import Task, TaskError, check_task, task_from_dict, task_to_dict
from signal_tasks.prune import prune

DONE_PCT = 100

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskList:
    """What tasks.json holds.

    Attributes:
        tasks: The valid tasks, in file order (entries that fail the checks are skipped).
        updated_at: ISO time of the last write, or None before the first.
    """

    tasks: tuple[Task, ...]
    updated_at: str | None


@dataclass(frozen=True)
class TaskChange:
    """The fields `set_task` changes; None leaves a field as it is (or its default on create)."""

    name: str | None = None
    pct: int | None = None
    status: str | None = None
    next: str | None = None
    you: str | None = None


def read_tasks(path: Path) -> TaskList:
    """The tasks in `path`; an empty list if there's no file yet.

    Raises:
        StateFileError: The file exists but can't be read.
    """
    payload = read_json_object(path)
    entries = payload.get("tasks")
    tasks = []
    for raw in entries if isinstance(entries, list) else []:
        try:
            tasks.append(task_from_dict(raw))
        except TaskError as error:
            log.warning("skipping a bad entry in %s: %s", path.name, error)
    updated_at = payload.get("updated_at")
    return TaskList(tuple(tasks), updated_at if isinstance(updated_at, str) else None)


def set_task(path: Path, task_id: str, change: TaskChange, now: datetime) -> Task:
    """Create the task or change the given fields of an existing one.

    A new task needs a name; its pct defaults to 0 and its status to queued.
    Leaving needs_you without a new `you` clears the old one.

    Raises:
        TaskError: A field breaks its rule (nothing is written).
        StateFileError: The file couldn't be locked, read or written.
    """
    with state_lock(_lock_path(path)):
        tasks = list(read_tasks(path).tasks)
        index = next((i for i, task in enumerate(tasks) if task.id == task_id), None)
        old = tasks[index] if index is not None else _new_task(task_id, change)
        task = check_task(_apply(old, change, now))
        if index is None:
            tasks.append(task)
        else:
            tasks[index] = task
        _write(path, tasks, now)
    return task


def mark_done(path: Path, task_id: str, now: datetime) -> Task:
    """Set the task to done at 100%, with nothing left for the owner.

    Raises:
        TaskError: No task has that id.
        StateFileError: The file couldn't be locked, read or written.
    """
    return set_task(path, _require_id(path, task_id), TaskChange(pct=DONE_PCT, status="done"), now)


def remove_task(path: Path, task_id: str, now: datetime) -> None:
    """Delete one task.

    Raises:
        TaskError: No task has that id.
        StateFileError: The file couldn't be locked, read or written.
    """
    with state_lock(_lock_path(path)):
        tasks = list(read_tasks(path).tasks)
        kept = [task for task in tasks if task.id != task_id]
        if len(kept) == len(tasks):
            raise TaskError(f"no task has the id {task_id!r}")
        _write(path, kept, now)


def _new_task(task_id: str, change: TaskChange) -> Task:
    if change.name is None:
        raise TaskError(f"there's no task {task_id!r} yet, so --name is needed to create it")
    return Task(task_id, change.name, 0, "queued", "", "", "")


def _apply(task: Task, change: TaskChange, now: datetime) -> Task:
    status = change.status if change.status is not None else task.status
    you = change.you if change.you is not None else (task.you if status == "needs_you" else "")
    return replace(
        task,
        name=change.name if change.name is not None else task.name,
        pct=change.pct if change.pct is not None else task.pct,
        status=status,
        next=change.next if change.next is not None else task.next,
        you=you,
        updated_at=now.isoformat(timespec="seconds"),
    )


def _require_id(path: Path, task_id: str) -> str:
    if not any(task.id == task_id for task in read_tasks(path).tasks):
        raise TaskError(f"no task has the id {task_id!r}")
    return task_id


def _write(path: Path, tasks: list[Task], now: datetime) -> None:
    kept = prune(tasks, now)
    payload = {
        "updated_at": now.isoformat(timespec="seconds"),
        "tasks": [task_to_dict(task) for task in kept],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, payload)


def _lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")
