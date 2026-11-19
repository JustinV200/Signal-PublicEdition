# calendar_tool.mcp_server

The stdio MCP server named `calendar`, which `calendar mcp` runs. Claude Code prefixes its tools `mcp__calendar__`.

## Tools

| Tool | Does | Annotations |
|---|---|---|
| `calendar_agenda` | The next `days` (1-60, default 14), with ids and flags | read-only |
| `calendar_create` | Adds an event: no guests, nobody notified, never asks | writes |
| `calendar_update` | Changes the title, times, location or description | destructive |
| `calendar_delete` | Deletes an event, an occurrence or (`series`) the series | destructive |
| `calendar_respond` | Answers an invitation (`accepted`, `declined`, `tentative`) | destructive |

`calendar_id` defaults to `primary`; `series` defaults to false (one occurrence). Update, delete and respond open the owner's Allow/Deny dialog for any event the tool didn't create, unless it's turned off in the config (see `changes/`).

Every result is one fixed, trusted line, then any Google-derived data as compact JSON inside `<untrusted_calendar_content>...</untrusted_calendar_content>` (`signal_untrusted.framed`, which escapes every `<`). The server instructions and each description say that content is data, never instructions. A delete returns the trusted line only.

## Public API

- `build_server(CalendarTools(actions)) -> MCPServer`: tests use it with an in-process `mcp.Client`.
- `run_stdio_server()`: the production server, wired through `service.build_actions()`. It starts without a sign-in; a call without one fails with "Not signed in yet. Run `calendar add`."
- `SERVER_NAME`, `TAG`.

## Files

`app.py` (registration), `tools.py` (handlers and framing), `descriptions.py` (model-facing text), `launch.py`.

## Depends on

`mcp==2.3.0`, `signal_untrusted`, `calendar_tool.service`, `calendar_tool.changes`, `calendar_tool.agenda`, `calendar_tool.errors`.
