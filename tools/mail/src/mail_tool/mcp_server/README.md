# mail_tool.mcp_server

The stdio MCP server named `mail`, which `mail mcp` runs. Claude Code prefixes its tools `mcp__mail__`.

## Tools

| Tool | Does | Annotations |
|---|---|---|
| `mail_accounts` | Lists aliases, emails and statuses | read-only |
| `mail_search` | Runs a Gmail query and returns summaries | read-only |
| `mail_read` | Returns one message as plain text, plus attachment names | read-only |
| `mail_thread` | Returns a conversation, oldest first | read-only |
| `mail_draft` | Creates a draft or a threaded reply draft; never sends | writes |
| `mail_send_draft` | Sends a draft after the owner clicks Allow | destructive |

`account` is an alias or an email address. Results are compact JSON text (no indent, to save tokens). Every tool that returns email text says in its description that the wrapped content is data, never instructions.

## Public API

- `build_server(MailTools(service)) -> MCPServer`: tests use it with an in-process `mcp.Client`.
- `run_stdio_server()`: the production server, wired through `service.build_service()`.

## Files

`app.py` (registration), `tools.py` (handlers), `descriptions.py` (model-facing text), `launch.py`.

## Depends on

`mcp==2.3.0`, `mail_tool.service`, `mail_tool.gmail` (`DraftContent`), `mail_tool.errors`.
