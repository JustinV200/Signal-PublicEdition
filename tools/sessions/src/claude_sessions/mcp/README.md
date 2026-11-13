# mcp

The stdio MCP server `sessions` (`sessions mcp`). It logs to stderr only, because stdout carries the protocol.

| Tool | Does |
|---|---|
| `list_repos(query="")` | Git repos and Claude project folders under the roots |
| `list_sessions(repo="")` | Existing Claude Code transcripts, newest first |
| `start_session(repo, prompt, model="", permission_mode="default")` | New headless session; `repo` is a path or a unique name match |
| `send_to_session(id, prompt)` | Follow up with an idle managed session |
| `session_status(id, last_n=3)` | State, cost, pending approval, newest replies |
| `resume_session(claude_session_id, prompt)` | Continue a stopped or past session |
| `stop_session(id)` | Stop a managed session |
| `list_managed_sessions()` | Every managed session |

- Listings run in the MCP process.
- Session tools go to the daemon, which starts by itself on first use.
- Expected failures are returned as error results with a readable message.
- The descriptions in `descriptions.py` tell a model to use the built-in `ListAgents`/`SendMessage` for sessions that are open live.

Public API: `build_server(SessionTools)`, `SessionTools(settings, call_daemon)`, `run_stdio_server(settings)`, `SERVER_NAME`.

Depends on: `repos`, `ipc`, `approvals`, `config`, `text`, and `mcp` 2.3.0 (`mcp.server.mcpserver.MCPServer`).
