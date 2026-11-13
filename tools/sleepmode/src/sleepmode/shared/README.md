# sleepmode.shared

Helpers that more than one sleepmode package uses.

## Public API

- `popen_detached(command, flags, cwd, output=None) -> Popen` starts a background process with no inherited handles and its streams on NUL, or on `output` (an open binary file the child alone writes). It tries `CREATE_BREAKAWAY_FROM_JOB` first, so the process outlives the MCP server or terminal that started it, and starts it inside the job if the job refuses. Used by `sleepmode.keeper` (the keeper), `sleepmode.lighting` (OpenRGB's SDK server) and `sleepmode.whiteboard_link` (the whiteboard daemon).
- `is_process_alive(pid, created=None)`: with `created`, a pid now used by a process that started at another time doesn't count. `process_creation_time(pid)` gives that time. Used by `sleepmode.keeper` (its own pid) and `sleepmode.whiteboard_link` (the whiteboard daemon's pid).

## Depends on

The standard library only (`subprocess`, `ctypes`).
