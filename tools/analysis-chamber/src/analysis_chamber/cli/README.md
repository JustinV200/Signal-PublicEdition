# analysis_chamber.cli

The `analysis-chamber` command line. `main(argv=None) -> int`; `build_parser()`.

Subcommands: `serve`, `mcp`, `cancel <id>`, `start <question>`, `approve <id> [--edits TEXT]
[--personal yes|no]`, `status <id>`, `list`, `ask <id> <question>`, `gpu -- <cmd...>`,
`kit build`, `install [--allow-shadow] <pkg...>` (installs into the venv of the run in the
current folder; exits 1 if there is no `manifest.json` there).

Output: client commands print the daemon's reply as indented JSON. A `DaemonError` prints
to stderr and exits 1, as does a `KitError` or `OSError` from `kit build`, `install` or `gpu`
(one stderr line). `gpu` exits with the wrapped command's exit code.

Depends on: `config`; `daemon`, `gpu`, `kit` and `mcp_server` (imported lazily inside each handler).
