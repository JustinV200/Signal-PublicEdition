# daemon

The process that holds live managed sessions (`sessions serve`).

- `SessionManager(ManagerDeps)`: `start`, `send`, `status`, `resume`, `stop`, `list`, `stop_all`. It persists every record after each change.
  - `load()` marks sessions that were live as `stopped`.
  - `resume` accepts a managed id or a Claude session id. An unmanaged session is adopted by looking up its transcript's `cwd`.
- `DaemonServer(manager, ListenSpec(host, port, token_file), on_shutdown)`: binds loopback only and requires the token on every request.
  - `bind()` takes the port alone; `start()` binds if needed, writes a fresh token to `token_file` only once the bind succeeded, then starts accepting connections. A second daemon that loses the port never replaces the live token.
  - A malformed or unauthenticated line gets one error reply, then the connection is closed.
  - Refusals become error replies; unexpected failures are logged and reported as internal errors.
- `SessionManager` checks every folder (start, resume, adopt) with `repos.require_inside_roots`.
- `serve(settings, approver=None, client_factory=create_sdk_client)`: wires the real parts together and runs until `shutdown` or Ctrl+C.
  - It binds the port before loading `sessions.json`, so a second daemon that can't bind never rewrites the live one's file. Then the server publishes the token in `.state/token` (`.state/token-<port>` on a non-default port).
  - Every session is stopped on the way out, before the port is released.
- `kill_children_with_daemon()` (`job_object.py`): puts the daemon in a `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` job, so a hard crash also kills its `claude.exe` processes and their MCP servers.
- `session/`: one managed session, its record, store and views (see its README).

Depends on: `daemon.session`, `ipc`, `approvals`, `notify`, `repos`, `sdk`, `config`, `tokens`, and `signal_hub_notify` (`packages/hubnotify`) for the `Notifier`.
