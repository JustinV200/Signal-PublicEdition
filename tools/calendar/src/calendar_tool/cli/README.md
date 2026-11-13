# calendar_tool.cli

The `calendar` command (`python -m calendar_tool.cli` runs the same thing).

## Public API

- `main(argv=None) -> int`: parses and runs `setup`, `add [--email]`, `agenda [--days N] [--json]` or `sync-cache`. A `CalendarError` prints `calendar: error: ...` to stderr and returns 2. Ctrl+C returns 130.

## Files

- `main.py`: the parser and error handling.
- `commands.py`: the handlers and `build_client()` (tests replace it with a fake).
- `sync_status.py`: saves each `sync-cache` outcome to `.state/sync_status.json` (`{"ok", "at", "kind", "message"}`, plus `"skipped"` calendar names), since the scheduled run has no stderr; `setup` prints it.
- `__main__.py`: `python -m calendar_tool.cli`, used by the scheduled task.

## Depends on

`calendar_tool.agenda`, `calendar_tool.auth`, `calendar_tool.google_api`, `calendar_tool.paths`, `calendar_tool.errors`.
