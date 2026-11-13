# audiohub.brain

The Claude Code session the user talks to by voice. It holds one persistent, multi-turn
`ClaudeSDKClient` (claude-agent-sdk) rooted at the repo. Claude's text replies come back as
events. Voice is a thin, fast layer: it runs its own quick tools (music, the whiteboard, the
brief, sleep mode, lookups) and hands everything else to the main Signal session.

## Public API (`audiohub.brain`)

- `ClaudeBrain(brain_settings, cwd, *, session_factory=SdkSession, on_background_text=None, on_tool_call=None, main_session=None, choice_path=BRAIN_CHOICE_PATH)`
  - `await start()` / `await close()`, or `async with ClaudeBrain(...) as brain:`
  - `async for event in brain.ask(text)` yields `ReplyText(text)` per assistant text block, then
    one `TurnDone(duration_s, cost_usd, is_error)`. `cost_usd` is that turn's own cost.
    `is_error` is also True for an interrupted turn.
  - `ask()` calls are serialised. If an `ask()` is abandoned mid-turn, the next one waits for
    that turn to finish. It also waits for a turn Claude started on its own, because the CLI
    would fold the request into that turn and never answer it with a result of its own.
  - Watchdog: a turn that shows no activity (no text, tool call or tool result) for
    `brain.turn_stall_timeout_s` (300 s) makes `ask()` raise `TurnStalledError`. The CLI is asked
    to stop that turn (waiting at most 5 s for it to confirm), and it is treated as running in the background, so its late text can't
    pass for the next reply. A turn being waited for (an earlier or injected one) is given up on
    after the same stretch with no activity. Activity resets the clock, so a busy turn can run
    for any length of time.
  - `interrupt()` while an `ask()` is still waiting for an earlier or injected turn cancels that
    request too: it is never sent, and `ask()` yields only an error `TurnDone`.
  - `on_background_text(text)`, sync or async, gets text from turns Claude starts on its own,
    e.g. when a background agent finishes or another session sends a message. That text never
    leaks into the next `ask()`.
  - `await interrupt()` stops the running turn, or an injected one. It does nothing when idle.
  - `on_tool_call(tool_name)` hears each tool call the permission gate allows, just before it
    runs (the voice loop's music pause uses it). It must return quickly; an error it raises is
    logged and the call still runs.
  - Model and effort: `brain.model` (default `sonnet`) and `brain.effort` (default `low`) are always passed explicitly, so the orchestrator's local `model`/`effortLevel` never reach voice. The console's voice pick in `choice_path` (`.cache/brain-choice.json`, checked by `signal_modelchoice`; an unlisted value is logged and ignored) goes on top, at connect and before each request. A new model goes through the SDK's live `set_model`. A new effort, which the CLI only takes at start, reconnects with `resume=<session id>` (taken from the last turn result), so the conversation carries on; that turn pays one CLI startup. If the reconnect fails, that request fails and the next one tries again, as a new conversation if resuming was what failed. The reconnect stops the old CLI, so background work started there (background agents, shells) is dropped.
  - MCP self-heal: before each request the keeper also reconnects, with resume, when `.mcp.json` under `cwd` has a new mtime (a session's server list is fixed at start), and otherwise asks the CLI for MCP status and reconnects each `failed` server (`connection/mcp_heal.py`). The status probe and each reconnect are capped at 5 s. A server whose reconnect fails or times out is skipped for 5 minutes, so it can't slow every turn; a failing status probe is logged and the turn goes ahead. A "stop" that arrives during this preparation means the request is never sent. A server that is connected but stale (old token, old code) reports as connected, so this can't fix it: the servers re-read their own tokens, and old code needs a hub restart.
  - `main_session` is the hand-off tool's sender (`handoff_tool.MainSessionHandoff`). `ask()`
    notes each request it sends there, so a hand-off quotes the owner's own words. None sends to
    the orchestrator `console claim` recorded; tests pass one with their own claim file.
- `TurnStalledError` (a `RuntimeError`): raised by `ask()` when the watchdog gives up on a turn.
- `VOICE_SYSTEM_APPEND`: voice-mode instructions appended to the `claude_code` system prompt.
- `BackgroundTextHandler`.
- `BrainSession` (`connect(resume=None)`, `send`, `events`, `interrupt`, `set_model`, `mcp_server_statuses`, `reconnect_mcp_server`, `disconnect`, `session_id`), `SessionFactory`, `SessionEvent`, `InjectedTurnDone`, `TurnActivity`: the
  session protocol, for injecting a fake. A `SessionFactory` gets the settings, cwd, the gate's
  decider and the hand-off tool's handler. `TurnActivity(is_subagent=False)` is a message that
  shows a turn is running but has nothing to speak (a tool call, a tool result, thinking).

## How it works

- `start()` connects the session and starts **one reader task** for the session's lifetime. It
  feeds every event to `TurnRouter`, which sends replies to the open `ask()` or to
  `on_background_text`. Reading continuously keeps the SDK's bounded buffer from filling between
  turns, which would stall permission callbacks. A result counts as ours when its `origin` is
  None or `"human"`; anything else (e.g. `"task-notification"`) is an injected turn.
- `TurnRouter` rules:
  - Any event with no `ask()` turn open starts an injected turn, as soon as it appears, text or
    not, except a subagent's `TurnActivity` (background agents stream those between turns).
    One that starts with no text is logged at INFO with the SDK message type that began it
    (`TurnActivity.source`, e.g. `UserMessage` for another session's prompt).
  - Any result, ours or injected, ends both the injected turn and the open `ask()` turn. If a
    request still gets folded into an injected turn (a race), that turn's result is the only one
    coming, so waiting for another would wedge the voice loop.
  - "Ignoring a turn result with no request waiting for it" in the log is a result labelled as
    ours (no origin) that arrived with no `ask()` open: an injected turn the CLI didn't label,
    or the late result of a request the watchdog or an injected result had already ended.
- `cwd` is the repo root. `setting_sources=["project", "local"]` loads CLAUDE.md / AGENTS.md,
  `.claude/settings*.json` and `.mcp.json`. User settings are left out so the user's global
  model and plugins don't slow the voice session (see `sdk_options.py`).
- `permission_mode="default"`, and `can_use_tool` goes through `permissions.PermissionGate`.
  A PreToolUse hook answers "ask" for every tool, so the CLI sends every call to the gate,
  including calls a settings allow rule matches. The gate never asks: it allows voice's own
  tools and the hand-off, and refuses everything else with a message telling Claude to hand
  the job off (`permissions/README.md`). `disallowed_tools` carries CLI deny rules that keep reads
  away from env files, any `.state/` or `.cache/` folder, the browser profile and screenshots,
  and the home folder's credential files (`SECRET_READ_DENY_RULES`) before the gate is asked.
- `tools` limits the built-in tools to Read, Glob, Grep and WebSearch (`VOICE_TOOLS`); MCP
  tools come on top. Besides the repo's `.mcp.json` servers,
  voice has its own in-process `voice` server (`sdk_tools.py`) with one tool,
  `hand_off_to_main_session`, which passes a job to the main Signal session without a
  question (`handoff_tool/README.md`). Agent, SendMessage, scheduling and remote
  tools are left out. Flag settings, which outrank every settings file, stop any settings file
  switching the session to bypassPermissions (`disableBypassPermissionsMode`), keep the
  account's claude.ai connectors such as Gmail out (`disableClaudeAiConnectors`), and skip
  settings-file hooks (`disableAllHooks`; the SDK callback hook still runs). CLI stderr is
  logged as warnings.

## Layout

| Module | Role |
|---|---|
| `claude_brain.py` | `ClaudeBrain`, the reader task |
| `turn_watchdog.py` | `TurnStalledError`, the stall watchdog |
| `connection/` | `protocol.py` (the `BrainSession` protocol, `SessionFactory`, `ToolCallHandler`) and `keeper.py` (`SessionKeeper`: opens the session, applies the voice pick, reconnects with resume) |
| `turn_router.py` | `TurnRouter`: which events reach `ask()` vs the background handler |
| `events.py` | `ReplyText`, `TurnDone`, `InjectedTurnDone`, `TurnActivity` |
| `voice_prompt.py` | `VOICE_SYSTEM_APPEND` |
| `permissions/` | the voice permission gate: allows voice's own tools, refuses the rest (own README) |
| `handoff_tool/` | the hand-off to the main Signal session (own README) |
| `sdk_options.py` | builds `ClaudeAgentOptions` (SDK adapter) |
| `sdk_messages.py` | SDK messages to session events (SDK adapter) |
| `sdk_session.py` | `SdkSession` wrapping `ClaudeSDKClient` (SDK adapter) |
| `sdk_tools.py` | voice's in-process MCP server, the hand-off tool (SDK adapter) |

Only the `sdk_*` modules import `claude_agent_sdk`.

## Depends on

- `audiohub.config` (`BrainSettings`, `ORCHESTRATOR_CLAIM_PATH`, `BRAIN_CHOICE_PATH`, `with_brain_choice`, which uses `signal_modelchoice`)
- `signal_orchestrator` (`packages/orchestrator`), through `handoff_tool`
- `claude-agent-sdk`, which bundles the Claude Code CLI. Auth comes from the existing login in
  `~/.claude`, or from `ANTHROPIC_API_KEY`.
