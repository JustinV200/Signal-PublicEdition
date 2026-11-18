# health

The console's own checks, as rows `{id, name, level, state, words, fix, command}`. `console doctor` prints them; the token-guarded `GET /api/health` sends them as `{rows: [...]}`.

Every check is a local read (files, the process table, the pipe listing), so the rows are the same with the server down, nothing is written, and no key or token is sent anywhere. No row carries a socket name, key or token; hook and hub errors are counted, never quoted.

Levels: **fail** means the console can't work (the page isn't built, a turn or session hook entry is missing, Edge is missing); `console doctor` exits 1. **attention** means it works but needs a look (server not running, another program on the port, no session linked or the linked one closed, no hook report since the session linked, hook errors in the last 24 hours, a hook in both settings files, the whiteboard off, errors in the hub's log). Every row that isn't ok has `fix`, one plain sentence, and `command` when one command fixes it (runnable as shown: from any folder for `console open`, else from the repo root).

- `row.py`: `HealthRow`, the levels, `SETUP_COMMAND` (`.\setup.cmd console`, the fix for what setup builds or writes) and `RECENT_WINDOW` (24 hours: older hook and hub errors are history).
- `inputs.py`: `HealthPaths`, every file the checks read (this checkout's by default; tests pass temp ones).
- `report.py`: `health_rows(paths, now=None)` runs every check in display order; a check that breaks becomes an attention row.
- `server_check.py`: the server row (daemon.json's process still running, via `local_api.server_port`) and `port_row(paths)`: who listens on the port, when it isn't the server daemon.json names. It names the other checkout (or program) and has fix words that read `console open --port <a free port>`; the row has no `command`, since that text isn't runnable as shown. `console open` asks `port_row` before it starts a server.
- `port_holder.py`: `find_port_holder(port)` reads the listening-socket table and the holder's exe and command line (and its two parents', since uv's venv launcher starts the base Python as a child). Nothing connects to the port. Without elevation every pid and exe can be read; a system process's command line can't, and then the row says only that another program holds the port.
- `claim_check.py`: present, open (`orchestrator.is_claim_alive`) and age (`orchestrator.claimed_ago`).
- `hook_settings.py`: the turn hook (4 events) and session hook (2) in `.claude/settings.json` or `.claude/settings.local.json`, and a hook in both (it would fire twice).
- `hook_activity.py`: the last reply the turn hook brought (the newest `claude` message in `history.jsonl`; attention when it's older than the claim's `claimedAt`, since history fills only while the server runs and is capped) and `hook.log` lines from the last 24 hours (older ones are history).
- `local_checks.py`: the built page, Edge, the whiteboard daemon (its `daemon.json` pid, still running and started no later than its `started_at`), and errors in the last 64 KB of `hub.log`.

Public API: `signal_console.health` (`health_rows`, `port_row`, `HealthPaths`, `HealthRow`, the levels, `SETUP_COMMAND`). Depends on `paths`, `state_files`, `local_api`, `open_hint`, `orchestrator`, `status` and `psutil`.
