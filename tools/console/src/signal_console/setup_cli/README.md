# setup_cli

The setup wizard's bridge to `tools/setup` (the console's Setup and Tools pages). It runs the setup CLI as a program (`uv run --project tools/setup --frozen --quiet setup ...`), never imports it, so the tools stay standalone and the CLI stays the single source of truth for tools, steps, settings and progress.

- `requests.py`: `build_call(body)` turns `{command, ...}` from the page into fixed CLI arguments. Commands: `intro`, `list`, `plan`, `status` (`--json` health), `tour` (`--json`), `wire` (`--yes`), `prereqs`, `verify`, `choose`, `apply`, `mark`, `config` (`--list`, or `--set`), `samples`. Ids are checked by shape and never start with `-`; free text goes as `--flag=value` or on stdin (pasted samples).
- `runner.py`: `SetupRunner` runs one command at a time (a second gets `SetupBusy`, a 409) with stdout and stderr merged and unbuffered, handing each line on as it comes. A page that goes away doesn't stop the command.
- `terminal.py`: `open_terminal(root, tool)` opens a PowerShell window on `setup.ps1 <tool>`, for steps that need the owner's own terminal (passwords, Windows Hello, typed client IDs).

Depends on `signal_console.launch` (clean environment). Used by `server/routes/setup.py`.
