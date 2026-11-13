# signal_mcpshim (packages/mcpshim)

A stdio proxy that Claude Code launches in place of an MCP server, so a server that dies comes back on its own. Claude Code never restarts a dead stdio server (see `refdocs/research/console-models-tasks-mcp.md` §3); the shim keeps Claude Code's pipe open and respawns the real server behind it.

```
uv run --project packages/mcpshim --frozen mcpshim -- <real server command...>
```

One shim per server, so tool names don't change.

What it does:

- Relays newline-delimited JSON-RPC both ways, including server-initiated requests and the client's replies. The server's stderr is inherited; the shim logs to stderr only.
- Passes the client's `initialize` through and returns the server's reply unchanged, so its capabilities and `instructions` reach Claude Code.
- When the server exits, for any reason, respawns it and replays `initialize` (id `mcpshim-init-<n>`, reply swallowed) plus `notifications/initialized` before relaying anything new.
- A request in flight to a server that dies gets a JSON-RPC error. A request that arrives mid-restart waits up to 15 s, then gets an error. A client reply to a dead server's request is dropped.
- Backs off between respawns (0.5 s doubling, 30 s cap), reset after 60 s of uptime.
- Never watches files. To reload a server's code, kill its process and the shim starts a fresh one.
- On stdin EOF it closes the server's stdin, waits 3 s, then kills the process tree (`taskkill /T` on Windows, so `uv run`'s grandchild isn't orphaned).

## Public API (`from signal_mcpshim import ...`)

- `main(argv=None) -> int`: the `mcpshim` command.
- `Shim(command, write_to_client, timings=None)`: the relay. Feed it client lines with `feed_client_line(line)` (None at EOF) on its event loop, and `await run()`.
- `ShimTimings`: every delay above, so tests can use tiny ones.

## Depends on

The standard library only (asyncio, json, threading).

## Tests

`uv run --frozen pytest`. They drive a `Shim` around `tests/fake_server.py`, a tiny fake MCP server.
