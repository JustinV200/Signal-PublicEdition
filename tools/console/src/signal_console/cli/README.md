# cli

The `console` command: `serve`, `open`, `claim`, `hub start|stop|status` and `tasks set|done|rm|show`. See the top-level README.

- `main.py`: argument parsing, and errors printed as one line with exit code 1.
- `commands.py`: `serve`, `claim` and `hub`.
- `tasks_command.py`: `console tasks`, which writes `.state/tasks.json` through `signal_tasks` (every field checked; a bad one prints one line and exits 1).
- `open_command.py`: `console open` starts the server if needed, gets a login key and opens Edge (or the default browser), optionally on a view and, for the setup wizard, a tool (`--view setup --tool mail`).

Public API: `signal_console.cli.main`. Depends on every other package.
