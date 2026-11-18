"""`console tasks set|done|rm|show`: the orchestrator reports its tasks for the Tasks page.

The orchestrator runs these from the repo root whenever a task changes state
(spawned, sent to review, PASS, needs the owner). They write
.state/tasks.json through signal_tasks, which checks every field; a bad one
prints one line and exits 1 (cli/main.py), writing nothing. `set` also claims
the console for its caller when no open session holds it (orchestrator/auto_claim.py).
"""

import argparse
import os
import sys
from datetime import datetime

from signal_tasks import (
    STATUS_NUMBERS,
    STATUS_WORDS,
    TaskChange,
    group_tasks,
    mark_done,
    read_tasks,
    remove_task,
    set_task,
)

from signal_console.orchestrator import claim_if_free
from signal_console.owner import read_owner_name
from signal_console.paths import ENV_FILE_PATH, STATE_DIR, TASKS_FILE


def add_tasks_parser(commands: argparse._SubParsersAction) -> None:
    """Register `console tasks` and its four actions on the top-level subparsers."""
    tasks = commands.add_parser("tasks", help="report Claude's tasks (the Tasks page)")
    actions = tasks.add_subparsers(required=True, metavar="action")

    set_parser = actions.add_parser("set", help="create a task or change some of its fields")
    set_parser.add_argument("id", help="short id: lowercase letters, digits, - and .")
    set_parser.add_argument("--name", help="what the task is (needed to create one)")
    set_parser.add_argument("--pct", type=int, help="rough percent done, 0-100")
    set_parser.add_argument("--status", choices=list(STATUS_NUMBERS))
    set_parser.add_argument("--next", help="the next step, one line")
    owner = read_owner_name(ENV_FILE_PATH)
    set_parser.add_argument("--you", help=f"what {owner} must do (required for needs_you)")
    set_parser.set_defaults(run=_run_set)

    done = actions.add_parser("done", help="mark a task done (100%%)")
    done.add_argument("id")
    done.set_defaults(run=_run_done)

    remove = actions.add_parser("rm", help="delete a task")
    remove.add_argument("id")
    remove.set_defaults(run=_run_remove)

    show = actions.add_parser("show", help="print the tasks in display order")
    show.set_defaults(run=_run_show)


def _run_set(args: argparse.Namespace) -> int:
    now = _now()
    change = TaskChange(args.name, args.pct, args.status, args.next, args.you)
    task = set_task(STATE_DIR / TASKS_FILE, args.id, change, now)
    print(_line(task.id, task.status, task.pct, task.name))
    # After the task is saved: a new session takes over a missing or closed claim.
    try:
        claim = claim_if_free(STATE_DIR, os.environ, now)
    except OSError as error:
        print(
            f"console: task {task.id} was saved, but linking the console failed ({error}). "
            "Run `console claim` to retry.",
            file=sys.stderr,
        )
        return 1
    if claim is not None:
        print(f"No open session held the console, so this one now does (as {claim.label!r}).")
    return 0


def _run_done(args: argparse.Namespace) -> int:
    task = mark_done(STATE_DIR / TASKS_FILE, args.id, _now())
    print(_line(task.id, task.status, task.pct, task.name))
    return 0


def _run_remove(args: argparse.Namespace) -> int:
    remove_task(STATE_DIR / TASKS_FILE, args.id, _now())
    print(f"Removed {args.id}.")
    return 0


def _run_show(args: argparse.Namespace) -> int:
    groups = group_tasks(read_tasks(STATE_DIR / TASKS_FILE).tasks)
    rows = (*groups.active, *groups.queued, *groups.done)
    if not rows:
        print("No tasks.")
    for task in rows:
        print(_line(task.id, task.status, task.pct, task.name))
        if task.you:
            print(f"    YOU: {task.you}")
        if task.next:
            print(f"    next: {task.next}")
    return 0


def _line(task_id: str, status: str, pct: int, name: str) -> str:
    return f"[{STATUS_NUMBERS[status]} {STATUS_WORDS[status]}] {task_id}  {name}  {pct}%"


def _now() -> datetime:
    return datetime.now().astimezone()
