# Morning run: keynotes and the TODO view's daily refresh

A per-user Windows scheduled task that runs every morning at 06:00, two actions in order:

1. `whiteboard keynotes`: one tool-less Claude (Sonnet) call reads the day's plan items and writes 2-4 keynote lines to `.state/keynotes.json`, which the idle and TODO views show today only. A failed call leaves no keynotes for the day, never an error on the board.
2. `whiteboard todo sync --if-running`, so today's date and the next 7 days roll over and yesterday's done items drop off.

Each sync run is `whiteboard todo sync --if-running` (through `uvw` and `pythonw`, so no console window opens, and with `uv run --frozen --no-sync`, so it never touches the venv a running daemon holds). It refreshes a running daemon and does nothing if the daemon isn't running: it never starts the daemon or lights the projector. A daemon syncs on its own when it starts. A run missed while the PC slept starts when it wakes.

## Register (owner, from the repo root, no admin)

```powershell
.\tools\whiteboard\schedule\register.ps1 -WhatIf   # show what it would do
.\tools\whiteboard\schedule\register.ps1           # register (add -RunNow to also run it once)
.\tools\whiteboard\schedule\unregister.ps1         # remove it again
```

The time and task name are in `schedule.psd1`. To change them, edit that file and run `register.ps1` again. After pulling a change to the task (such as the keynotes step), run `register.ps1` again: it replaces the task. Both scripts take `-TaskName` to try things with a throwaway name. The layout is the same as `tools/mail-digest`'s scheduled task.

## Files

- `schedule.psd1`: task name, path, time and time limit.
- `register.ps1`, `unregister.ps1`: create or remove the task.
