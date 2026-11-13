# sleepmode.schedule

When to wake, and the scheduled task that does it.

## Public API

- `parse_wake_time(text, now) -> datetime` reads `07:00`, `7`, `7am`, `7:30 pm`, `19:30` (the next time that comes round) or an ISO date-time such as `2026-10-20T07:00` (must be in the future; an offset is converted to local time). Raises `ValueError`.
- `WakeScheduler(task, xml_dir, run=run_hidden)`:
  - `schedule(when)` registers the one-shot task with `schtasks /Create /XML ... /F`, replacing any earlier one.
  - `cancel() -> bool` deletes it if it exists.
  - Both raise `ScheduleError` when schtasks refuses, and `subprocess.TimeoutExpired` when it hangs. `SCHEDULER_FAILURES` is the tuple of everything they can raise.
- `WakeTask(name, command, arguments, working_dir, time_limit)` and `task_xml(task, when)` build the XML.
- `create_args`, `query_args`, `delete_args` build the schtasks command lines.
- `run_hidden(args)` runs a console program with `CREATE_NO_WINDOW` and a 15 s timeout (`SCHTASKS_TIMEOUT_S`), decoding its output with `errors="replace"`.

## The task

- It's named `Signal sleep mode wake`, in the Task Scheduler root folder.
- It runs the venv's `pythonw.exe -m sleepmode wake --reason schedule`, as the current user, only while logged on, without elevation (no admin needed).
- `StartWhenAvailable` runs it late if its time was missed.
- It expires a day after its time and then deletes itself, in case `wake` couldn't remove it.

## Depends on

The standard library only (`subprocess`, `xml.sax.saxutils`).
