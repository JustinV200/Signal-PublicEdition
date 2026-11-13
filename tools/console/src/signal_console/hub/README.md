# hub

Controls the voice hub process: the one `console hub start` launched, or one started elsewhere.

- `start_hub(state_dir)` starts audiohub detached, with its output in `.state/hub.log`, and records its pid and start time in `.state/hub.json`. It refuses if a hub is already running.
- `find_console_hub(state_dir)` returns that process while it's alive. Matching on start time means a reused pid is never taken for the hub.
- `find_hub(record_path)` returns the process named in the hub's own record (`tools/audiohub/.cache/hub.json`, written by every `audiohub run` once its IPC port is bound), but only if its pid and start time match and it runs from `tools/audiohub` (the recorded pid is the base interpreter, whose command line runs the venv's `audiohub.exe`). It never deletes the record: a stale one reads as no hub.
- `stop_hub(state_dir, hub_record_path)` stops the console's hub, or, when there is none (no record, or a stale one, which it removes), the one `find_hub` returns, in one call. It first asks the hub to shut down cleanly over its kernel IPC (`shutdown.py`: `{"token","command":"shutdown"}` with the token from `tools/audiohub/.cache/ipc-token`), so the hub restores the ducked or paused music and closes its audio. Only if the hub doesn't agree (it isn't listening yet, or is wedged) or hasn't exited after 10 s (`GRACEFUL_EXIT_TIMEOUT_S`) does it kill the hub's own processes. Those are the recorded process and the descendants that run from `tools/audiohub` (uv's launcher, the hub's Python, the brain's bundled `claude.exe`), found only through each other. Nothing else under the hub is killed: the brain's other MCP servers exit when `claude.exe`'s pipes close, and the daemons they start (whiteboard, sessions, sleep keeper) are meant to outlive them. It forgets the console's record only once the hub's processes are dead (or the record names no live hub), and raises `HubError`, which the CLI prints, if the kill fails.

- `shutdown.py`: `request_hub_shutdown(token_path, port) -> bool` and `wait_for_exit(process, timeout_s) -> bool`. It speaks audiohub's wire format without importing audiohub. `stop_hub` takes the request as a parameter, so tests never stop a real hub.

Public API: `signal_console.hub`. Depends on `psutil`, `launch`, `process_record`, `process_tree`, `status` and `state_files`.
