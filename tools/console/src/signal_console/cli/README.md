# cli

The `console` command: `serve`, `open`, `claim`, `hub start|stop|status`, `doctor` and `tasks set|done|rm|show`. See the top-level README.

- `main.py`: argument parsing, and errors printed as one line with exit code 1.
- `commands.py`: `serve` (logs to `.state/server.log` too, and exits 1 after logging why the server stopped on an error), `claim` (replaces any claim; with no `--label`, the label is the local time) and `hub`.
- `tasks_command.py`: `console tasks`, which writes `.state/tasks.json` through `signal_tasks` (every field checked; a bad one prints one line and exits 1). After saving, `set` claims the console for its caller when no open session holds it (`orchestrator.claim_if_free`).
- `doctor_command.py`: `console doctor` prints one line per `health` row (level word, name, words, then `Fix:` and `Run:` when not ok) and exits 1 only on a fail row. `--summary-json` adds the first fail row as a last JSON line `{words, fix, command}` for setup's verify check. Read-only; works with the server down.
- `server_log.py`: the log format; `log_to_server_log(state_dir)`, which adds `.state/server.log` as a log file unless stderr already is that file (a server `console open` started, whose output goes there); and `print_to_server_log(state_dir)`, which points stdout and stderr at that file for `open` under pythonw (no console).
- `open_command.py`: `console open` stops at once with `.\setup.cmd console` when `web/dist/index.html` is missing (it never builds), starts the server if needed, prints every `health` row that isn't ok, then opens Edge (or the default browser), optionally on a view and, for the setup wizard, a tool (`--view setup --tool mail`).
- `server_start.py`: `open`'s server start. `login_key` asks this checkout's running server for a one-time key (only the server daemon.json names). `start_server` refuses a port another program holds (`health.port_row`, a local read that never connects), prints `Starting the console server...`, starts `serve` detached with its output in `server.log`, keeps its `Popen`, and if it exits during the wait raises `OpenError` with the log's last line (and the `--port` way out on a bind error).

Public API: `signal_console.cli.main`. Depends on every other package.
