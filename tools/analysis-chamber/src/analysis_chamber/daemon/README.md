# analysis_chamber.daemon

The `analysis-chamber serve` daemon: a loopback HTTP API over the run registry,
the run queue, startup resume, and the blocking client the MCP server and CLI use.
The contract is in [../../../DESIGN.md](../../../DESIGN.md).

## Public API

`from analysis_chamber.daemon import serve, start_daemon, RunningDaemon, Backend, DaemonClient, DaemonError, DaemonNotRunningError`

- `serve(config)`: rotating log in `log_dir/analysis-chamber.log`, puts the process in a
  kill-on-close Windows job (gpu's `KillOnCloseJob`; agent CLIs die with it), then runs
  until interrupted.
- `await start_daemon(config, backend) -> RunningDaemon` (`.port`, `await .close()`):
  takes an exclusive lock on `state_dir/daemon.lock` (a second daemon fails), resumes runs,
  binds 127.0.0.1 on a random port, writes `state_dir/daemon.json` `{port, token, pid}`
  owner-only.
- `Backend`: the injected phase functions and objects (`wiring.default_backend` is the real one).
  `make_hooks(on_update, notifier)` gets a per-run notifier that sends one closed notice per run.
- `DaemonClient(state_dir)`: `start`, `approve`, `status`, `list(timeout_s=30)`, `ask`, `cancel`, each a dict.
  `start`, `approve` and `ask` block for the agent turn (1 h timeout); the rest 30 s.
  Raises `DaemonError` (not running, refused, dropped); not running (no `daemon.json`, or a refused connection) is its subclass `DaemonNotRunningError`.

## Layout

- `api/`: request parser (strict, size-capped, token checked before the body), routes, server.
- `engine/`: `Chamber` (registry and route operations), `Scheduler` (FIFO, `max_parallel_runs`),
  `drive_run` (one run's task), `persist` (leak guard before every manifest write),
  `placement` (new-run path checks, atomic move at approval), views.
- `state_file.py`, `client.py`, `serve.py`, `wiring.py`, `logs.py`, `process.py` (daemon lock,
  kill-on-close job).

## Rules it enforces

- A bad, oversized or unauthenticated request gets no reply; the connection just closes.
- Every manifest write runs `check_run_location` first; a `LeakError` fails the run in memory
  and nothing is written.
- Manifest writes are synchronous calls on the one event-loop thread, so a run's writes
  never interleave.
- Shutdown cancels active runs first. `persist` saves the CANCELLED that phases records on
  any cancel as `running` unless it came from `/cancel`, whoever writes during the unwind (the
  pipeline or a mid-run ask), and no closed notice goes out, so the next start re-queues
  `running` and `queued` runs in created order. `awaiting_approval` runs just wait.
- A failed or cancelled run is recorded and announced once (`run.closed`): a `/cancel` that
  outlasts its 30 s wait records it, and the late unwind then writes and announces nothing.
- A plan draft cut off mid-turn (shutdown, crash, dropped request) fails the run with
  "plan draft interrupted", at once or on the next start; the user starts it again.
- If startup fails after resuming runs, they're stopped (not cancelled) and the lock freed;
  `close()` always removes daemon.json and frees the lock, even if stopping fails.
- Approval renames a non-personal run into `analyses_root` in one same-volume rename; roots on
  different volumes are refused, and a failed move leaves the run private and unapproved.
- Plan, revise and ask turns on one run take turns (per-run lock): one live writer per session.
- `/start` refuses run folders over 100 characters (Windows MAX_PATH, see the session-resume spike).

## Depends on

`config`, `runs`, `guard`, `gpu` (`KillOnCloseJob`); at runtime (`wiring.py` only) `agents`, `phases`, `kit`, `notify`.
