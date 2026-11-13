# cli

The `sessions` command (`main(argv=None)`, `build_parser()`). Commands:

- `local_commands.py`: `serve`, `mcp` and `repos` run in this process.
- `daemon_commands.py`: `list`, `start`, `send`, `status`, `resume`, `stop` and `shutdown` each make one daemon request. All except `shutdown` start the daemon first if needed.

Errors the user can fix print one line and exit with code 2.

Depends on: `config`, `repos`, `ipc`, `approvals`, and lazily `daemon` and `mcp`.
