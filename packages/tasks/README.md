# signal_tasks (packages/tasks)

The orchestrator's task list as a library: the `tasks.json` schema, the field checks, pruning of old done tasks, the display order every view shares, and the usage line shown beside it. Design: `refdocs/research/console-models-tasks-mcp.md` §2.

The path is always the caller's. The console keeps the file at `tools/console/.state/tasks.json`; the whiteboard reads the same file.

## The file

```json
{"updated_at": "<ISO>", "tasks": [
  {"id": "brief-p2", "name": "Brief phase 2", "pct": 60, "status": "review",
   "next": "fresh reviewer on the hub diff", "you": "", "updated_at": "<ISO>"}]}
```

- `status`: `review` (1), `building` (2), `needs_you` (3), `queued` (4), `done` (5), the board's status numbers (`STATUS_NUMBERS`, `STATUS_WORDS`).
- `id`: lowercase letters, digits, `-` and `.`, up to 40 characters. `name` up to 60, `next` 140, `you` 200, each one line. `pct` is a whole number 0-100.
- `you`: what the owner must do; required for `needs_you`, and cleared when a task leaves `needs_you` without a new one.
- Done tasks older than 24 h are pruned on every write, keeping at most the newest 20.
- A hand-edited entry that fails the checks is skipped (and logged) when read.

## Public API (`from signal_tasks import ...`)

- `read_tasks(path) -> TaskList(tasks, updated_at)`.
- `set_task(path, id, TaskChange(name, pct, status, next, you), now) -> Task`: upsert; `None` fields stay as they are (a new task needs `name`, and starts `queued` at 0%). Raises `TaskError` (a `ValueError`) for a bad field, writing nothing.
- `mark_done(path, id, now)`, `remove_task(path, id, now)`: `TaskError` for an unknown id.
- `group_tasks(tasks) -> TaskGroups(active, queued, done)`: active by pct (highest first), queued in file order, done newest first; `needs_you` and `overall_pct` (the mean over active and queued).
- `read_usage(path, now) -> UsageSummary | None`: the 5-hour and weekly windows (None once reset), fresh agents over all sessions and the file's age. `None` means "unreadable right now, keep your last copy" (the usage README's reader rules); a missing file is `NO_USAGE`.
- `prune(tasks, now)`, `check_task(task)`, `task_to_dict(task)`.
- `StateFileError` (re-exported from `signal_jsonstate`): the file couldn't be locked, read or written.

Writes take `<path>.lock` through `signal_jsonstate` and replace the file atomically, so readers need no lock.

## Depends on

`signal_jsonstate` (`packages/jsonstate`). Add it with `uv add --editable ../../packages/tasks` (and list `signal-jsonstate` in the project's `[tool.uv.sources]` too).

## Tests

`uv run --frozen --no-sync pytest`
