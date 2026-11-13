# Agenda cache refresh

A per-user Windows scheduled task that runs `calendar sync-cache` every 10 minutes, so `tools/calendar/.state/agenda.json` stays current for the idle board. No Claude is involved, and it only reads the calendar.

Each run goes through `uvw` and `pythonw`, so no console window opens, and uses `uv run --frozen --no-sync`, so it never changes the venv. A failed run leaves the old cache and shows a non-zero last-run result in Task Scheduler. A run missed while the PC slept starts when it wakes.

## Register (owner, from the repo root, no admin)

Sign in first (`calendar add`, see ../SETUP.md). Then:

```powershell
.\tools\calendar\schedule\register.ps1 -WhatIf   # show what it would do
.\tools\calendar\schedule\register.ps1 -RunNow   # register and run it once
.\tools\calendar\schedule\unregister.ps1         # remove it again
```

Registering refuses if the tool's venv isn't synced (`uv sync --project tools/calendar --frozen`). The interval and task name are in `schedule.psd1`; edit it and run `register.ps1` again to change them. Both scripts take `-TaskName` for a throwaway test name.

## Files

- `schedule.psd1`: task name, path, interval and time limit.
- `register.ps1`, `unregister.ps1`: create or remove the task.
