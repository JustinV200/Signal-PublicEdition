# analysis_chamber.mcp_server

The stdio MCP server `analysis-chamber` with exactly five tools, thin wrappers over
`DaemonClient`: `chamber_start`, `chamber_approve`, `chamber_status`, `chamber_list`,
`chamber_ask`. Cancel is CLI only (`analysis-chamber cancel <id>`).

- Public API: `build_server(state_dir)`, `run_stdio_server(state_dir)`, `SERVER_NAME`.
- Results are the daemon's dicts as JSON text. A `DaemonError` becomes a tool error with the
  client's own message (it already says how to start the daemon).
- `descriptions.py` holds the model-facing text (plan check with the user, personal flag,
  when to publish); edit it there.
- Depends on: `analysis_chamber.daemon` (imported lazily), `mcp`.
