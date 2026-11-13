# sessions

Lets Claude, from this repo (the VS Code chat or the audiohub voice assistant), start and drive Claude Code sessions in the owner's other local repos. It has three parts:

- **A daemon** (`sessions serve`) holds one live, headless Claude Code session per managed session.
- **An MCP server** (`sessions mcp`, server name `sessions`) exposes the daemon and the repo/transcript listings as tools.
- **A CLI** offers the same operations for a person.

Each package under `src/claude_sessions/` has its own README.

## Live sessions vs. managed sessions

| You want to... | Use |
|---|---|
| Talk to a session that is already open live: VS Code, a terminal, Remote Control or the cloud | Claude Code's built-in `ListAgents` and `SendMessage` tools. Nothing to install. |
| Start a new headless session in another local repo | `start_session` |
| Continue a past session (from `~/.claude/projects`) headlessly | `list_sessions`, then `resume_session` |
| Check on or follow up with a session this tool started | `session_status`, `send_to_session`, `stop_session`, `list_managed_sessions` |

Don't resume a session that is still open live somewhere else. Two writers on one transcript conflict.

## How a managed session behaves

- It runs in the repo folder with the owner's normal setup:
  - user, project and local settings
  - CLAUDE.md
  - the repo's MCP servers
  - the `claude_code` system prompt
- Any tool call the CLI would prompt for opens a topmost Allow/Deny dialog (`signal_confirm`) on the PC. The dialog shows the repo and the command, path or URL.
  - Deny is the default button, and Allow has no keyboard shortcut.
  - The call is denied after 120 s, counting time spent queued behind other dialogs.
  - Dialogs appear one at a time, and the voice note for each comes when its dialog shows.
- `permission_mode` can be `default`, `acceptEdits` or `plan`.
  - `acceptEdits` runs file edits without a dialog, and also the Bash commands `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp` and `sed`, and the PowerShell cmdlets `Set-Content`, `Add-Content`, `Clear-Content` and `Remove-Item` (and their aliases) on paths inside the repo. That means it can delete or overwrite files unapproved; everything else still asks.
  - `bypassPermissions` is always refused.
  - The CLI is also told to disable it, so no settings file can turn it on.
- The CLI also gets deny rules that block reads and writes that name one of the owner's secret files, in any repo, with no dialog to click through. See `src/claude_sessions/sdk/README.md`.
  - They cover `.env` files, the `.state` and `.cache` folders (mail sign-ins, `google_client.json`, the whiteboard, console, sessions and hub tokens), the browser profile and screenshots, the vault store, `~/.ssh` and Claude Code's credentials.
  - `.env.example` and other `.env.*` files are blocked too.
  - The whole of every `.state` and `.cache` folder is blocked, tool logs included. To debug a tool's log, use a normal session, or approve a script that reads it in the dialog.
  - They come through flag settings, which outrank every settings file except managed settings. Deny rules merge from all sources anyway, so no repo's settings can lift them.
  - They don't stop commands that read files without naming them, such as `grep -r TOKEN .`, and 8.3 short names (`ENV~1`) may slip past.
- The audiohub voice hub (127.0.0.1:8765) hears about three events. Each message carries the hub's token from `tools/audiohub/.cache/ipc-token`. If the hub isn't running (or that file is missing), the message is logged and dropped. Delivery is shared with the browser tool through `signal_hub_notify` (`packages/hubnotify`).
  - A turn finishes: normal priority, "OtherRepo session finished: ..."
  - A session errors: high priority.
  - A tool call needs approval: high priority.
- Sessions only run in local folders inside the repo roots, after links and junctions are followed. This applies to start, resume and adopting a past session's folder. Network (UNC) and `\\?\` paths are refused, because a folder's `.claude` settings and hooks run without a dialog.
- The daemon only answers requests that carry the token in `.state/token`, which is readable by the owner only. It hangs up on any malformed or unauthenticated line. The CLI and MCP server read the token themselves.
- Session metadata is kept in `.state/sessions.json`, so after a daemon restart `resume_session` continues a session by its managed id or its Claude session id.
- "Repos" are the git repos under `C:\src` (depth 4), plus folders under `C:\src` where Claude Code has already run. Many project folders, such as `C:\src\OtherRepo`, aren't git repos themselves.

## Setup

From `tools/sessions`:

```
uv sync
uv run sessions --help
```

Register the MCP server in the repo root's `.mcp.json`. The key must be `sessions`, because it sets the `mcp__sessions__` tool prefix.

```json
{
  "mcpServers": {
    "sessions": {
      "command": "uv",
      "args": ["run", "--project", "tools/sessions", "--frozen", "sessions", "mcp"]
    }
  }
}
```

The daemon starts by itself in the background the first time a tool or CLI command needs it.
- Its log is `.state/daemon.log`.
- It runs in a kill-on-close job object, so if it dies, its `claude.exe` processes and their MCP servers die too.
- It survives the MCP server and VS Code closing.
- `sessions shutdown` stops it and its sessions.

It runs hidden (`CREATE_NO_WINDOW`), so the `claude.exe` processes it starts don't open console windows.

Optional environment overrides:

| Variable | Sets | Default |
|---|---|---|
| `SESSIONS_REPO_ROOTS` | Repo roots, `;`-separated | `C:\src` |
| `SESSIONS_MAX_DEPTH` | Search depth below each root | 4 |
| `SESSIONS_DAEMON_PORT` | Daemon port | 8766 |
| `SESSIONS_HUB_PORT` | Voice hub port | 8765 |
| `SESSIONS_STATE_DIR` | State folder | `.state/` |

## CLI

```
sessions repos [QUERY]                 git repos and Claude project folders
sessions start REPO PROMPT [--model sonnet] [--mode default|acceptEdits|plan]
sessions send ID PROMPT                follow up with an idle session
sessions status ID [--last N]          state, cost, pending approval, newest replies
sessions resume SESSION PROMPT         continue a stopped or past session
sessions stop ID
sessions list                          managed sessions, newest first
sessions serve [--port N]              run the daemon in the foreground
sessions mcp                           the stdio MCP server
sessions shutdown                      stop all sessions and the daemon
```

`REPO` is a path, or a repo name or unique part of one.

## Development

```
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

Tests mirror `src/claude_sessions/` and use a fake SDK client, a fake approver and a fake hub, with no network. The Windows dialog and the real Claude CLI are tested by hand through the CLI.
