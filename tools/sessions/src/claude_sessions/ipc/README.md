# ipc

The daemon's wire protocol, its client, and auto-start.

- Protocol: newline-delimited UTF-8 JSON over loopback TCP (127.0.0.1:8766).
  - Request: `{"op", "args", "token"}`; the token is checked first, with `hmac.compare_digest`. Reply: `{"ok": true, "result"}` or `{"ok": false, "error"}`.
  - Ops: `ping`, `list`, `start`, `send`, `status`, `resume`, `stop`, `shutdown`.
  - Both ends validate every request: argument names and types, a 1 MiB line cap, a 100,000-character prompt cap, the id format, `last_n` of 0-10, and the permission mode.
- `DaemonEndpoint(host, port, token)`, `daemon_endpoint(settings)`: the address plus the token read from `.state/token` (`.state/token-<port>` for a non-default port). With no token file, the daemon counts as not running.
- `call_daemon(endpoint, op, args)`: one request. Raises `DaemonNotRunningError`, `DaemonRequestError`, `ProtocolError` or `TimeoutError`.
- `ensure_daemon(settings)`: start `python -m claude_sessions serve` in the background if nothing answers, then wait up to 20 s for `ping`.
  - If the port answers but refuses the token, or answers with something that isn't the daemon, it raises `DaemonStartError` at once rather than starting a daemon that can't bind.
- `call_running_daemon(settings, op, args)`: sends the request straight away; only when nothing answers does it run `ensure_daemon` and retry once.
  - Flags are `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, plus `CREATE_BREAKAWAY_FROM_JOB` when the parent's job allows it.
  - `DETACHED_PROCESS` isn't used: it gives every `claude.exe` child its own visible console window.
  - Output goes to `.state/daemon.log`.

Depends on: `config`, `approvals`, `tokens`.
