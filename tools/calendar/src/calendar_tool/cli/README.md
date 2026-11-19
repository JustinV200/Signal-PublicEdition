# calendar_tool.cli

The `calendar` command (`python -m calendar_tool.cli` runs the same thing).

## Public API

- `main(argv=None) -> int`: parses and runs `setup`, `add [--email]`, `agenda [--days N] [--json]`, `sync-cache`, `mcp`, `create`, `update`, `delete` or `respond` (arguments in the tool's README). A `CalendarError` prints `calendar: error: ...` to stderr and returns 2. Ctrl+C returns 130.

## Files

- `main.py`: the parser and error handling.
- `commands.py`: the read and setup handlers, `build_client()` (tests replace it with a fake), and `agenda_line()`, which ends each agenda line with the ids the write commands take.
- `write_parser.py`, `write_commands.py`: the write subcommands' arguments and handlers, over `service.build_actions()`. They open the owner's Allow/Deny dialog the same way the MCP tools do.
- `__main__.py`: `python -m calendar_tool.cli`, used by the scheduled task.

## Depends on

`calendar_tool.agenda`, `calendar_tool.auth`, `calendar_tool.changes`, `calendar_tool.service`, `calendar_tool.mcp_server`, `calendar_tool.google_api`, `calendar_tool.paths`, `calendar_tool.errors`.
