# cli

The `sessions` command (`main(argv=None)`, `build_parser()`). Commands:

- `local_commands.py`: `serve`, `mcp`, `repos` and `check` run in this process. `check` is the setup tool's health check: one JSON line `{words, fix, command}` saying how many repos it finds and whether the daemon answers a ping within 4 s (it never starts one, and not running passes; something on its port that doesn't answer as it, a stale token or a hung daemon, reads `daemon not answering`, exit 1).
- `daemon_commands.py`: `list`, `start`, `send`, `status`, `resume`, `stop` and `shutdown` each make one daemon request. All except `shutdown` start the daemon first if needed.

Errors the user can fix print one line and exit with code 2.

Depends on: `config`, `repos`, `ipc`, `approvals`, and lazily `daemon` and `mcp`.
