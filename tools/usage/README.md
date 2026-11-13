# usage

Keeps one small JSON file current with the owner's Claude Code usage: the 5-hour and weekly rate-limit windows, and how many subagents are running. The whiteboard reads that file (its display is a separate task). Stdlib only, Python 3.12, uv.

It never reads the OAuth credentials file or anything under `~/.claude`. Its only inputs are the JSON that Claude Code pipes to the status line and hooks on stdin.

## Sources

- **Status line** ([docs](https://code.claude.com/docs/en/statusline)). The stdin JSON has `rate_limits.five_hour.used_percentage` (0-100) and `rate_limits.five_hour.resets_at` (Unix epoch seconds), and the same for `seven_day`.
  - `rate_limits` is there only for Pro and Max subscribers, and only after the session's first API response. Either window can be missing.
  - The command runs at session start, after each assistant message, and every `refreshInterval` seconds (minimum 1). Updates are debounced at 300 ms, and a run still going when the next one starts is cancelled.
  - Whatever it prints is the status line, so it prints `5h 42% · wk 18% · 2 agents (5 all)`: this session's subagents, then the total across sessions when it differs.
- **`SubagentStart` / `SubagentStop` hooks** ([docs](https://code.claude.com/docs/en/hooks)). Their input has `session_id`, `agent_id` and `agent_type`.
  - `SubagentStart` fires again when a subagent resumes, and for each message an agent team teammate handles.
  - `SubagentStop` also fires for Claude Code's internal agents (prompt suggestions, `/btw`).

## Setup

1. `cd tools/usage && uv sync`.
2. Add the status line to your user settings, `~/.claude/settings.json`, so every session reports usage:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "C:/src/Signal/tools/usage/.venv/Scripts/python.exe -I -m usage.statusline",
       "refreshInterval": 30
     }
   }
   ```
   - On Windows the command runs through Git Bash (or PowerShell without it), so the path needs forward slashes. Backslashes get eaten and the line goes blank.
   - `-I` (isolated mode, which includes `-P`) keeps the session's cwd and `PYTHONPATH` off `sys.path`. The status line runs in every repo, and without `-I` a stray `json.py` in one would shadow the stdlib: the line would crash, and that file would run.
3. Add the hooks to `.claude/settings.local.json`, next to its other keys:
   ```json
   {
     "hooks": {
       "SubagentStart": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "C:/src/Signal/tools/usage/.venv/Scripts/python.exe",
               "args": ["-I", "-m", "usage.hook"],
               "timeout": 5
             }
           ]
         }
       ],
       "SubagentStop": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "C:/src/Signal/tools/usage/.venv/Scripts/python.exe",
               "args": ["-I", "-m", "usage.hook"],
               "timeout": 5
             }
           ]
         }
       ]
     }
   }
   ```
   - `args` runs it in exec form, with no shell. `-I` is there for the same reason as on the status line.
   - The hooks are left synchronous on purpose. `async: true` is supported, but each async run is its own background process, so a stop could land before its start and leave a phantom agent for 2 h. A run takes about 90 ms.
   - With no `matcher`, the hooks fire for every agent type.

Both need the folder's workspace trust accepted in interactive sessions.

## The state file: `.state/usage.json`

```json
{
  "five_hour": {"used_pct": 42.3, "resets_at": "2026-10-20T02:28:55-04:00", "changed_at": "<ISO>"},
  "seven_day": {"used_pct": 18.0, "resets_at": "2026-10-24T00:28:55-04:00", "changed_at": "<ISO>"},
  "active_subagents": 1,
  "sessions": {
    "<session_id>": {
      "agents": [{"id": "agent-1", "type": "Explore", "seen_at": "<ISO>"}],
      "updated_at": "<ISO>"
    }
  },
  "updated_at": "<ISO>"
}
```

- Times are ISO 8601 local time with the UTC offset. A window is `null` when it isn't known.
- `active_subagents` is the total over all sessions.
- A window's `changed_at` is when its `used_pct` or `resets_at` last changed. Re-sending the same values keeps it.
- `updated_at` is the last write by any status line or hook. A run that changes nothing doesn't write, so it's the time of the last real change.

### How values are merged

- **Usage is account-wide**, but each session only knows the values from its own last API response, and an idle session re-sends those on every refresh. Usage only grows within a window, so:
  - for the same window (reset times within 5 minutes), the higher percentage wins;
  - a later reset time is a newer window and replaces the old one.
- **A window a session doesn't send** keeps the known value until its `resets_at` passes. Then it's dropped.
- **Subagents** are a set per session: a start adds the id (a repeat start just refreshes it), and a stop removes it. An agent not seen for 2 hours (`STALE_AGENT_HOURS`) is pruned on every write (each hook event and each status line refresh), because an agent killed with TaskStop, or whose session died, never fires its stop. (Trade-off: a live agent that runs over 2 hours without a resume drops out of the count until its next start.) A session with no agents left is dropped.

### Concurrency

Several sessions write at once. Every write takes `.state/usage.json.lock`, reads, merges, then writes a per-process temp file and `os.replace`s it.
- A lock older than 2 s (`STALE_LOCK_S`) was left by a killed run, so it's broken.
- The status line waits up to 1 s for the lock, then skips that update (it runs again soon) and prints the numbers merged in memory. The hook waits up to 3 s, past the stale age, so a dead writer's lock can't cost it a start or stop.
- Breaking a lock can, rarely, let two writers in at once, and one update is lost. See the `shortcut:` comment in `store.py`.

Readers need no lock, because they only ever see a whole file. They should still:
- open, read and close the file quickly. Windows can't replace a file a reader has open, and a writer only retries for about 0.1 s;
- poll at about 1 Hz or slower;
- on a `PermissionError` or bad JSON, keep the last value and retry on the next tick.

## Failures

The status line never fails. If it can't write (lock timeout, or a reader holding the file), it still prints the known numbers. On any other error it prints `usage --`. Either way it exits 0. The hook prints nothing and always exits 0. Both log failures to `.state/errors.log`, which starts over past 256 KiB. A log line has only the error's type and message, never the input.

## CLI

`uv run --project tools/usage --frozen --no-sync usage show` prints the state file.

## Caveats for the display

- **Values go stale.** Nothing writes the file while no session is open, and idle sessions re-send old values, so the display should show the age of each window's `changed_at`.
- **The display must check times itself.** It should treat a window whose `resets_at` has passed as unknown, and ignore agents whose `seen_at` is over 2 hours old, because the file is only cleaned up on the next write.
- **Freshness is limited.** The numbers are only as fresh as the newest API response among the open sessions.
- **Only Signal's subagents are counted.** The hooks live in this repo's `.claude/settings.local.json`, so subagents of sessions in other repos aren't counted. For those, put the same hooks in `~/.claude/settings.json` with the absolute python path.

## Check live

Not yet confirmed in a real session:
- **Start and stop ids match.** The hooks docs' examples show different `agent_id`s for `SubagentStart` and `SubagentStop`. If the real ones differ too, no stop removes its start, and every agent stays counted for 2 h.
- **Interrupted agents.** Whether pressing Esc on a subagent, or killing the session, fires `SubagentStop`. If not, those agents stay counted until the 2 h prune.
- **VS Code.** The VS Code extension may not run status lines. Then usage only updates from terminal sessions, though the hooks still count subagents.
- **Worktree sessions.** The hooks use an absolute path, so a session in a git worktree should still count its subagents; confirm one does.

If phantom agents show up, the `subagentStatusLine` setting (see the status line docs) could reconcile the count.

## Layout

`src/usage/`:
- `statusline.py` and `hook.py` are the entry points, and `cli.py` is `usage show`.
- `rate_limits.py` and `agents.py` hold the pure merge rules.
- `store.py` holds the locked atomic write.
- `times.py` and `paths.py` hold time helpers and paths, and `error_log.py` is the error log.

## Tests

`uv run --frozen --no-sync pytest` covers the window merge, garbage stdin on the status line, the subagent set (start, stop, repeat start, prune), a huge stop input, stale-lock breaking and the bounded lock wait, concurrent writers, and keeping input out of the error log.
