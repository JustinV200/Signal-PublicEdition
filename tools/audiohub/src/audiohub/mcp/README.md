# audiohub.mcp

A stdio MCP server, run with `audiohub mcp`. It gives any Claude Code session in this repo, including the voice brain, these tools:
- `notify`: speak to the user through the voice hub's kernel
- `music_*`: control the music

The server is named `audiohub`, so Claude Code shows the tools as `mcp__audiohub__<tool>`. The voice brain auto-allows that prefix.

## Tools

| Tool | Does | Backed by |
|---|---|---|
| `notify(text, priority="normal", source="claude-code")` | Queues `text` on the running hub to be spoken | `kernel.send_notification` |
| `music_now_playing()` | Title, artist, album, playing or paused | `MusicController.now_playing` |
| `music_play()` / `music_pause()` | Resume / pause | `play` / `pause` |
| `music_next()` / `music_previous()` | Skip forward / back | `next` / `previous` |
| `music_set_volume(percent)` | Spotify volume, 0-100 | `set_volume` |
| `music_search_and_play(query, kind="track")` | Search and play the best match (`track`, `album`, `playlist`, `artist`) | `search_and_play` |
| `music_play_liked(shuffle=None)` | Play the user's Liked Songs; `true`/`false` sets shuffle first, `None` leaves it | `play_liked` |
| `music_queue(query)` | Add the best track match to the queue | `queue` |

Every tool returns one plain sentence:
- If the hub isn't running, or refuses or drops the message, `notify` says the message was not delivered and why. While the owner is asleep or away the hub drops notes, and `notify` returns "Not spoken (dropped: the owner is asleep). Don't resend it; ...". When the hub isn't running, it tells the model to tell the user so, not to start the hub itself.
- `MusicUnavailable` and `UnsupportedOperation` come back as their speakable message.
- A bad argument (volume out of range, blank query) fails music's shared checks before any call, and comes back as an MCP error result.
- Anything unexpected is logged to stderr and reported as a tool error.

The music controller is built once at startup with `music.create_controller(settings.music)`. That makes no network or Windows calls.

## Registering it

Add this to the repo root's `.mcp.json`. The key must be `audiohub`, because it sets the tool prefix.

```json
{
  "mcpServers": {
    "audiohub": {
      "command": "uv",
      "args": ["run", "--env-file", ".env", "--project", "tools/audiohub", "--frozen", "audiohub", "mcp"]
    }
  }
}
```

`--env-file .env` loads the repo-root `.env` (copy `.env.example`). uv fails to start if the file is missing.

## Public API

- `run_stdio_server(settings)` serves on stdin/stdout until the client disconnects. `audiohub mcp` calls it.
- `build_server(notify_tool, music_tools) -> MCPServer` registers every tool. Tests pass it fakes.
- `NotifyTool(ipc_settings, send=send_notification)` backs `notify`.
- `MusicTools(controller)` backs the `music_*` tools.
- `format_now_playing(now) -> str`
- `SERVER_NAME` (`"audiohub"`)

## Notes

- stdout is the protocol channel, so nothing here prints. Logs go to stderr.
- The official SDK is v2 (`mcp==2.3.0`). It uses `mcp.server.mcpserver.MCPServer`, which replaced v1's `FastMCP`.
- Every import is absolute. Inside this package, `import mcp` always resolves to the SDK, never to `audiohub.mcp`.
- The server module is named `app.py` so it isn't confused with the SDK's `mcp.server`.

## Files

| File | Contents |
|---|---|
| `app.py` | `build_server`: names and registers the tools |
| `launch.py` | `run_stdio_server`: real kernel client and music controller, stdio transport |
| `notify_tool.py` | `NotifyTool`: delivery and failure messages |
| `music_tools.py` | `MusicTools`, `format_now_playing`: controller calls and error mapping |
| `descriptions.py` | Server instructions and every tool description |

## Dependencies

- The `mcp` SDK
- `audiohub.config`: `IpcSettings`, `Settings`
- `audiohub.kernel`: `send_notification` and its errors
- `audiohub.music`: `MusicController`, `create_controller`, `NowPlaying`, the `check_*` argument checks and the errors
