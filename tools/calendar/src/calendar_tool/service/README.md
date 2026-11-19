# calendar_tool.service

What the CLI's write commands and the MCP server both run: the agenda read and the four writes, wired to a sign-in, the gate and the agenda cache.

## Public API

- `CalendarActions(Backend)`: `agenda(days=14) -> dict` (the detailed `agenda_payload`, days 1-60), and `create`, `update`, `delete`, `respond`, each returning `WriteResult(event, is_board_refreshed)`.
  - Each call opens the client and reads the gate setting fresh, so a new `calendar add` or an edited `calendar.toml` counts without a restart.
  - After a successful write it refreshes the idle board's cache (`agenda.refresh_cache`); a failed refresh doesn't undo the write.
- `Backend(build_client, build_gate, cache_path, status_path, zone=None)`: where those come from (tests pass fakes).
- `build_actions()`: the production wiring (`auth.open_client`, `.state/calendar.toml`, `.state/agenda.json`).
- `gate_from_settings(config_path, zone=None)`: the real `ChangeGate`.
- `NOT_REFRESHED`: the line the CLI and MCP server print when a write's cache refresh failed.

## Files

`actions.py`, `factory.py`.

## Depends on

`calendar_tool.agenda`, `calendar_tool.changes`, `calendar_tool.auth`, `calendar_tool.google_api`, `calendar_tool.paths`, `calendar_tool.errors`.
