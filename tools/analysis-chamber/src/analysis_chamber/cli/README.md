# analysis_chamber.cli

The `analysis-chamber` command line. `main(argv=None) -> int`; `build_parser()`.

Subcommands: `serve`, `mcp`, `cancel <id>`, `start <question>`, `approve <id> [--edits TEXT]
[--personal yes|no]`, `status <id>`, `list`, `ask <id> <question>`, `gpu -- <cmd...>`,
`kit build`, `install [--allow-shadow] <pkg...>` (installs into the venv of the run in the
current folder; exits 1 if there is no `manifest.json` there).

`check` is the setup tool's health check. It never starts the daemon: it prints one JSON line
`{words, fix, command}`, `running, N runs` (exit 0), or exit 1 with `installed, kit not built`
(and the `kit build` command), `installed, daemon not running` (and the `serve` command), or
`installed, daemon not answering` (no command) when it runs but answers wrongly or not
within 4 s.

Output: client commands print the daemon's reply as indented JSON. A `DaemonError` prints
to stderr and exits 1, as does a `KitError` or `OSError` from `kit build`, `install` or `gpu`
(one stderr line). `gpu` exits with the wrapped command's exit code.

Depends on: `config`; `daemon`, `gpu`, `kit` and `mcp_server` (imported lazily inside each handler).
