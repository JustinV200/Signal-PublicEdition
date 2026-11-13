# Signal console

A local web app that fronts the owner's Claude Code **orchestrator session**. Whatever the owner types goes to the orchestrator as a plain-language request, and the orchestrator does the work with its own tools. Otherwise the console *reads* status on its own: the voice hub, the whiteboard, the devices, the task list and whether the orchestrator is busy.

**The owner's own clicks act directly**, without the orchestrator. They run only on the owner's click in the logged-in page (token and origin checks), never on a message or an agent's request:

- **The buttons** (voice Start/Stop, board Send to projector, to-do list, idle board, Update, Realign, Full calibrate). `POST /api/action` runs each one in the server, deterministically, from a fixed list: voice through the same code as `console hub start|stop`, the board through the `whiteboard` CLI with fixed arguments (see `src/signal_console/actions/README.md`). The result shows on the action's row in the feed.
- **The Away/Here toggle** on the Devices page. `POST /api/away` turns the brief's away mode on or off directly (`signal_brief.away_on`/`away_off`, the same as `brief away on|off`), without asking the orchestrator.
- **The setup window** (the Setup and Tools tabs). `POST /api/setup/run` runs one command of the setup CLI (`tools/setup`) from a fixed list and streams its output; `POST /api/setup/terminal` opens a PowerShell window on `setup.ps1 <tool>` for steps that take a secret. See `src/signal_console/setup_cli/README.md`.
- **The model strip's pickers** (the page's Models tab). `POST /api/models` writes two allowlisted settings keys, `model` and `effortLevel`, in `.claude/settings.local.json` (for every new Signal session), and voice's `tools/audiohub/.cache/brain-choice.json`. Nothing else, and only values from fixed lists (see Security).

The camera view is a read like the other status reads: it shows the webcam and changes nothing.

- `src/signal_console/`: the Python backend (HTTP server, CLI, hooks). This README covers it.
- `web/`: the React/TypeScript frontend, built to `web/dist/` and served by the backend. It has its own docs.

## Setup

1. Install once: `uv sync --project tools/console`.
2. **Claim the orchestrator.** From the orchestrator session's own Bash or PowerShell tool, run:
   ```
   uv run --project tools/console --frozen --no-sync console claim --label "orchestrator"
   ```
   Claude Code gives each session's tools that session's inbox address and token (`CLAUDE_CODE_MESSAGING_SOCKET`, `CLAUDE_CODE_MESSAGING_TOKEN`). `claim` saves them to `.state/orchestrator.json`, readable only by you. A successor orchestrator (after a handoff) runs `claim` again.
3. **Add the turn hook** to `.claude/settings.local.json` so the console knows when the orchestrator is working and shows its replies. The same command goes under four events (the first shown in full; `Stop` and `StopFailure` are the same, and `Notification` adds `"matcher": "idle_prompt"` beside `"hooks"`):
   ```json
   {
     "hooks": {
       "UserPromptSubmit": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "${CLAUDE_PROJECT_DIR}/tools/console/.venv/Scripts/python.exe",
               "args": ["-m", "signal_console.hooks.turn"],
               "async": true
             }
           ]
         }
       ]
     }
   }
   ```
   The hook fires for every session in the repo, and does nothing unless it's running in the claimed session. It's async, never prints anything (plain stdout from `UserPromptSubmit` would become context Claude sees) and always exits 0.

   **The session hook** (`-m signal_console.hooks.session`, the same command shape, also `"async": true`) goes under `SessionStart` and `PostModelSwitch`. It records each session's model in `.state/session-models.json`, so the model strip can show what the claimed orchestrator runs now. It follows the same no-stdout, exit-0 contract.
4. **Open it:** `uv run --project tools/console --frozen --no-sync console open`. This starts the server in the background if it isn't running, then opens an Edge app window logged in with a one-time key.

## CLI

| Command | What it does |
| --- | --- |
| `console serve [--port 8790]` | Run the server in the foreground. |
| `console open [--port 8790] [--view V] [--tool T]` | Start the server if needed (detached, log in `.state/server.log`), then open `msedge --app=http://127.0.0.1:<port>/#k=<key>` (or the default browser without Edge). `--view setup --tool mail` opens on the setup wizard at that tool (`&v=setup&t=mail`); `setup` and `/setup` use it. |
| `console claim [--label NAME]` | Make the calling Claude Code session the orchestrator. |
| `console hub start\|stop\|status` | Start the voice hub detached (`uv run --env-file .env --project tools/audiohub --frozen --no-sync audiohub run` from the repo root, output in `.state/hub.log`), stop it, or report. `start` refuses if a hub is already running. `stop` stops the hub it started, or else the one named in the hub's own record (`tools/audiohub/.cache/hub.json`, which every `audiohub run` writes), so a hub started in a terminal stops too. It asks the hub to shut down cleanly first (over its kernel IPC, so the music is restored), and kills it only if it hasn't exited after 10 s. A kill takes only the hub's own processes; daemons that its MCP servers started keep running. |
| `console tasks set ID [--name N] [--pct P] [--status S] [--next T] [--you T]` | Create a task or change only the fields given (a new one needs `--name` and starts `queued` at 0%). `--status` is `review`, `building`, `needs_you` (needs `--you`), `queued` or `done`. Checked by `signal_tasks`: id is lowercase letters, digits, `-` and `.`; pct 0-100; one-line text. |
| `console tasks done ID` / `rm ID` / `show` | Mark done (100%), delete, or print the list in display order. |

The console's voice buttons run the same code as `hub start` and `hub stop` in the server. The orchestrator runs `tasks set` whenever a task changes state (AGENTS.md section 3). For example:

```
uv run --project tools/console --frozen --no-sync console tasks set brief-p2 --name "Brief phase 2" --pct 60 --status review --next "fresh reviewer on the hub diff"
uv run --project tools/console --frozen --no-sync console tasks set brief-p2 --status needs_you --you "say yes to the hook"
uv run --project tools/console --frozen --no-sync console tasks done brief-p2
```

## How it talks to the orchestrator

**Sending** goes through the shared `signal_orchestrator` package (`packages/orchestrator`), which the voice hub's hand-off uses too, over Claude Code's cross-session inbox (a named pipe), [documented here](https://code.claude.com/docs/en/cross-session-messaging#the-sessions-inbox-socket). The first line is the documented auth line, `{"type":"auth","token":"<token>"}`. Because it carries the session's own token, Claude Code counts the message as coming from the session's own child, so it delivers the message even though the orchestrator runs with bypassPermissions.

The message line, `{"type":"user","message":{"role":"user","content":"<text>"}}`, is **not documented**. It's the frame Claude Code's own sender writes, taken from the source of `claude.exe` 2.1.301 and confirmed with a probe. It's an internal format and may change in a later Claude Code version. If sends report `failed`, or say `sent` but never arrive, check this first (`inbox.py` in `packages/orchestrator`). The sender reports `failed` when the pipe can't be opened, or when Claude Code closes the connection straight away (which is what happens when the token is wrong).

Every message starts with `[Signal console] the owner: ...`, because the inbox doesn't show the sender's name. Buttons send nothing to the orchestrator.

**The marker is a label only, never consent.** Any process that holds the session's inbox token (anything the session itself runs, for one) can write the same words. The orchestrator should weigh a marked message on its content, the same as any other.

**The voice hub sends here too.** When the voice agent gets a job beyond its quick tools (code, settings, anything complicated), it reads the same claim file and sends one message starting with `[Signal voice]`, straight away and without a spoken question. The message quotes the owner's recent words as the hub transcribed them, apart from the voice agent's summary, and asks the orchestrator to treat a summary that doesn't match them as suspect. That marker is a label only too. The hand-off message itself doesn't show in the console's feed, though the orchestrator's reply does (through the turn hook). See `tools/audiohub/src/audiohub/brain/handoff_tool/README.md`.

When the claim changes (a different session or label, or the claim found when the server starts), the feed shows a `note` event saying where requests now go, so a claim the owner didn't make is visible.

**Replies and the busy status** come from the turn hook, which POSTs each event to `/api/hook/turn`:

- `UserPromptSubmit` starts a turn. It also fires on turns Claude Code starts by itself (a background agent finishing, an inbox message), so those show too.
- `Stop` ends it, with `last_assistant_message` (shown as Claude's reply) and the count of `background_tasks`. `StopFailure` (an API error) ends it too.
- `Notification` `idle_prompt` ends a turn, but only one whose start is at least 60 s older than it: a late idle prompt from the last turn can't end an inbox turn.

Each report carries `at`, stamped when the hook process started. Async hooks can land out of order, so a start and an end within 2 s of each other count as one turn; that fails towards `idle`, and the next hook corrects it. Interrupts fire no hook, so a turn with no hook (and no subagent change in `tools/usage/.state/usage.json`) for 10 minutes reads as stale. The states the page shows:

| State | When | Shows |
|---|---|---|
| working | a start, no end yet | `working 0:42` (+ ` · 5 agents`) |
| agents | no turn, but the session's subagents run | `waiting on 5 agents` |
| idle | no turn, no agents | `idle` |
| stale | working, no hook for 10 min | `no word from Claude for 12 min (interrupted?)` |
| unknown | no hook since the server started | `status unknown until Claude's next turn` |

Agents are the session's entries in `usage.json` seen in the last 2 hours. After a turn ends, that count is checked against Stop's `background_tasks`; when they disagree the lower one shows, with a `?`. A delivered request reads `sent` until the start hook arrives: the console never marks Claude busy by itself.

## Security

- Listens on 127.0.0.1 only. The `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`, which blocks DNS rebinding.
- Any `Origin` header must be the server's own, and the page's non-GET requests must send one. No CORS headers are ever sent.
- Login: `console open` gets a one-time key (single use, valid 60 s) and puts it in the URL fragment. The page trades it at `/api/login` for a random session token (`{"token": ...}`). Each login mints a new token; the server keeps the newest 8 in memory only, so restarting the server logs every page out.
- All of `/api/*` needs that token in the `X-Console-Token` header (401 without it), compared in constant time, except `/api/login` and the local routes (`/api/hook/turn`, `/api/local/login-key`). Those take `.state/local-key` as `X-Console-Key`, also compared in constant time. The page reads the event stream with a streaming `fetch`, because `EventSource` can't send headers.
- There's no cookie on purpose: browsers send a 127.0.0.1 cookie to every port on 127.0.0.1, so any other local server would receive it. A header only goes where the page's own script sends it.
- The hook and the CLI send the local key (and the hook its reply) only to the port in `daemon.json`, and only while the process recorded there (pid and start time) still runs. A file left behind by a crashed server never sends them to whatever holds that port now.
- Every response carries a strict CSP, `nosniff` and `no-referrer`. Request bodies are capped at 64 KB. Rejected connections are closed.
- The camera proxy (`GET /api/camera/stream`) sits behind the same token and origin checks. The server adds the whiteboard's `X-Signal-Token` itself; the page gets only the JPEG stream, never the token. The page shows frames as `blob:` images, the one addition to the CSP's `img-src`.
- `POST /api/action`, `POST /api/away` and `POST /api/models` are the only routes that change something without the orchestrator (see the top). `/api/action` takes `{action, args?}`: the action must be one of the fixed seven, and the one free string, a save name, must be in the whiteboard's current save list. It's passed to the whiteboard CLI as one list argument after `--`, never through a shell. Voice actions share one lock and board actions another, so a second click while one runs gets 409 (no two hubs, no two calibrations). `/api/away` takes `{on: bool, until?: text}` (until is at most 40 characters, read by `signal_brief.parse_until`).
- `POST /api/setup/run` takes `{command, ...}`; `setup_cli.build_call` turns it into fixed setup CLI arguments (a list, never a shell): ids are checked by shape and can't start with `-`, free text goes as `--flag=value` (one line, at most 1000 characters) or on stdin (pasted samples, at most 60,000). Commands that write (apply, mark, choose, wire, config `--set`, samples) run one at a time, so a second gets 409; read-only ones (list, status, plan...) run beside them. `wire --yes` is the owner's click on Write this after the page has shown `setup plan`. A page that closes mid-install doesn't stop the command. `POST /api/setup/terminal {tool}` starts only `powershell -NoExit -File setup.ps1 <tool>`.
- `POST /api/models` takes `{target, field, index}`. The index points into a fixed server-side list (`signal_modelchoice`: the documented model aliases, and the efforts `low` to `xhigh`), never a free string. Orchestrator lists start with "use my user settings", which removes the key. The settings writer (`models/settings_writer.py`) only ever touches `model` and `effortLevel`; refuses a file that's missing or doesn't parse as a JSON object (it's never replaced with `{}`); copies the old bytes to `.state/settings.local.bak.json`; and re-reads the file just before the atomic write, writing only if it's unchanged (one retry, then it refuses). A Claude Code write landing between that re-read and the replace can still be lost; the backup covers it. The first write reformats the file (`indent=1`). The voice brain re-checks `brain-choice.json` against the same lists when it reads it.
- Static files: a path with a backslash, a colon, NUL, an absolute path or a `..` segment never reaches the filesystem; it gets `index.html`.
- `.state/` is locked to the current user every time it's ensured (each start), and the secret files are locked before anything is written to them. If a lock fails, the write fails too.

## State (`tools/console/.state/`, gitignored)

| File | What it holds |
| --- | --- |
| `daemon.json` | The running server's pid, start time and port. |
| `local-key` | The secret that the hook and CLI send. |
| `orchestrator.json` | The claimed inbox: socket, token, label. The voice hub reads it for hand-offs. |
| `history.jsonl` | The last 200 message, delivery, voice and note events, replayed when a page connects. |
| `hub.json` | The pid and start time of the hub that `console hub start` launched. |
| `hub.log` | That hub's output, read for the phase and the voice feed. |
| `hub.prev.log` | The `hub.log` from before the last start, kept so a crashed hub's reason survives. |
| `server.log` | Output of a server that `console open` started. |
| `hook.log` | Turn and session hook failures. |
| `session-models.json` | `{session_id: {model, at}}` for the 20 newest sessions, from the session hook; and its `.lock`. |
| `settings.local.bak.json` | `.claude/settings.local.json` as it was before the model strip's last write. |
| `models.lock` | Held while a model strip pick is written. |
| `tasks.json` | The orchestrator's task list (`console tasks`; format in `packages/tasks`), and `tasks.json.lock`. |

Voice phase and feed only work for a hub started by `console hub start`. For a hub started some other way, the console shows `running` with no phase (Stop still works on it). Hub lines written while the server was down never reach the feed.

## Layout

`actions/` (the buttons: checking a click, running it), `orchestrator/` (claim file, chat wording; the claim type and inbox sender come from `packages/orchestrator`), `status/` (hub probe and log parsing, whiteboard reader, device rows), `away/` (the Away/Here toggle), `hub/` (hub process control), `turns/` (the orchestrator's turn state), `models/` (the model strip: settings writer, session models, voice's pick), `server/` (aiohttp app, events, routes, security), `hooks/` (turn and session hooks), `setup_cli/` (the setup window's bridge to the setup CLI), `cli/`. Each has its own README.
