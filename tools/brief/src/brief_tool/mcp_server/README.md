# brief_tool.mcp_server

The stdio MCP server named `brief` (tools are `mcp__brief__<name>`; the prompt hook relies on that name).

- `app.py`: `build_server(BriefTools, AwayTools)` registers the tools with their annotations.
- `brief_tools.py`: `brief_me`, `brief_ack`, `brief_log`, `brief_resolve`, `brief_get`, `brief_undo`.
- `away_tools.py`: `away_on`, `away_off`, `away_status`. The CLI's `away` commands call these too.
- `calls.py`: `call_in_thread` runs the blocking work off the event loop and turns `ValueError` and `BriefLogError` into `ToolError`.
- `descriptions.py`: the model-facing instructions and tool descriptions.

Depends on: `mcp`, `signal_brief`, `signal_untrusted`, `brief_tool.surface`, `brief_tool.wording`.
