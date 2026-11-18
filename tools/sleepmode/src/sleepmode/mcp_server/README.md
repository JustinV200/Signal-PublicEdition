# sleepmode.mcp_server

A stdio MCP server, run with `sleepmode mcp`. It's named `sleepmode`, so Claude Code shows the tools as `mcp__sleepmode__<tool>`.

## Tools

| Tool | Does |
|---|---|
| `sleep_mode_on(wake_at="")` | `SleepMode.sleep`: monitors off or black, the night sky on the projector, the optional wake task. Called again while on, it updates the sleep; `""` then keeps the wake time. |
| `sleep_mode_off()` | `SleepMode.wake`: everything back. Safe when already awake. |
| `sleep_mode_status()` | `SleepMode.status`: on or off, the wake time, each display, keeper health. Read-only. |

Each tool answers in the same plain text as the CLI (`sleepmode.control.describe_*`). A bad `wake_at` or a `SleepModeError` comes back as a tool error. The work runs in a worker thread.

## Public API

- `run_stdio_server(sleep_mode)` serves until stdin closes.
- `build_server(tools) -> MCPServer` and `SleepTools(sleep_mode)`: tests can build them around a `SleepMode` with fakes.
- `SERVER_NAME` (`"sleepmode"`).

## Depends on

The `mcp` SDK (`mcp==2.3.0`, `MCPServer`), and `sleepmode.control`.
