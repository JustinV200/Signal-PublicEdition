# turns

The claimed orchestrator's turn state: `working`, `agents`, `idle`, `stale` or `unknown`.

- `tracker.py`: `TurnTracker` folds the turn hook's reports (`TurnReport`: phase `start`/`end`/`idle`, session id, `at`, background task count) into a state. Its docstring holds the ordering rules (a start and end within 2 s are one turn; `idle` only ends a turn 60 s old; 10 min with no activity is stale). `status(now, usage_agents)` returns the `turn` object in `/api/state`: `{state, startedAt, lastActivityAt, agents, agentsUnsure}`, times in epoch ms. Pure logic; callers pass the clock.
- `usage_agents.py`: `UsageAgents(path).read(session_id, now)` counts the session's subagents in `tools/usage/.state/usage.json` seen in the last 2 h, and gives its last usage hook time (activity that keeps a turn from going stale). It follows usage's reader rules: re-read only on a new mtime, and keep the last good copy on a `PermissionError` or bad JSON.

Public API: `signal_console.turns`. Stdlib only.
