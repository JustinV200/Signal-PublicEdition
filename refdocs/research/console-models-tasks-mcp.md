# Console: models, tasks, MCP, status and board buttons

Design, 2026-10-20. Covers the owner's asks:
- model and effort switching (§1)
- an Active tasks page (§2)
- MCP servers that are always there (§3)
- a truthful busy status (§4)
- whiteboard Realign and Update buttons (§5)
- stopping a hub started outside the console (§6)

Claude Code claims cite code.claude.com/docs pages read today, or the bundled `claude.exe` (2.1.301 in audiohub's SDK, 2.1.304 in the VS Code extension). **Untested** marks anything not yet seen working.

## 1. Model and effort

### 1.1 What Claude Code allows

- **Inbox commands don't run.** "A command in the message's text, such as `/compact`, arrives as plain text. Claude Code never executes it" (cross-session-messaging). The receiving Claude is also told never to change configuration because another session asked. So the console can't send `/model` or `/effort`, and it can't ask the orchestrator to edit settings.
- **`model`, `effortLevel` and `modelSettings` are read once, at session start** (settings, "When edits take effect"). Settings files are watched and hot-reloaded, but these keys aren't, so an edit only reaches the next session. Resumed sessions keep their transcript's model.
- **Live switches happen only in a UI.** In VS Code, clicking the model name under the prompt box opens the picker, which has an Effort row (vs-code). Remote Control can also switch both, but model-config calls only the effort pick session-only. Not pursued here.
- **Precedence.**
  - Model: `/model` > `--model` > `ANTHROPIC_MODEL` > settings `model`.
  - Effort: `CLAUDE_CODE_EFFORT_LEVEL`/`--effort`/`/effort` > saved settings > the model's default.
  - Across settings files, "the highest-precedence settings file that sets either an `effortLevel` for that model or a top-level `effortLevel` that applies to that model decides" (settings-reference, `modelSettings`). A top-level `effortLevel` in local settings applies to every model. So a local `effortLevel` beats the user `modelSettings["claude-opus-5-5"]` entry.
- **Thinking amount is effort.** Thinking can't be turned off on Opus 5.5, Sonnet 5.5, Haiku 5.5 or Fable (model-config).
- **Reading the current state:**
  - `SessionStart` input has `model`, which is sometimes omitted.
  - `PostModelSwitch` gives `to_model`.
  - `Stop` input has `effort.level`, and `$CLAUDE_EFFORT` is set for hooks (hooks).

### 1.2 Voice (audiohub)

`brain/sdk_options.py` passes `model=brain.model or None`. `brain.model` defaults to `""`, which means the CLI default, because user settings are left out of `SETTING_SOURCES`. No effort is passed.

The SDK (claude-agent-sdk 0.2.168) has `ClaudeAgentOptions.effort` (`--effort`, start-only), a live public `ClaudeSDKClient.set_model()`, and a `resume` option. The brain keeps no session id and never resumes today.

### 1.3 Design

One **Model** strip in the console status area, with two rows.

**Orchestrator row.** It shows `now: opus-5-5 · medium` and `new Signal sessions: [model ▾] [effort ▾]`.

- **Where `now` comes from.** `SessionStart` fires before `console claim` runs, so the hook can't know whether its session is the claimed one.
  - A new `signal_console.hooks.session` (for `SessionStart` and `PostModelSwitch`) runs in every session. It records `{session_id: {model, at}}` in `.state/session-models.json`, keeping the last 20.
  - Sessions start concurrently, so the write takes the `jsonstate` lock (§2.1).
  - The server only shows a value that matches a short model-id pattern (`^[a-z0-9][a-z0-9.\-\[\]]{0,63}$`), else `model unknown`. A bad value only affects the display.
  - The turn hooks (§4) record the claimed session's id. The console looks the model up by that id.
  - `PostModelSwitch` updates the entry.
  - Fallback while the model is unknown (omitted after `/clear`, or a session that started before the hooks): `now: model unknown · medium`. Effort comes from each Stop's `effort.level`.
- **The writer.** A pick makes the console server write `model` and/or `effortLevel` into `.claude/settings.local.json`. Its limits:
  1. **Allowlist.** Only those two keys are ever written, and the request sends an index into a fixed server-side list, never a free string.
     - Models are exactly the documented aliases (model-config): `default`, `best`, `fable`, `opus`, `sonnet`, `haiku`, `opus[1m]`, `sonnet[1m]`, `opusplan`.
     - Efforts are `low`, `medium`, `high`, `xhigh`; `max` isn't accepted in settings.
     - Each list also has a "use my user settings" entry, which removes the key from the local file.
  2. **Parse or refuse.** The file must parse as a JSON object. If it's missing, unreadable or malformed, the write is refused (`can't update settings: file doesn't parse`). It's never replaced with `{}`. The tolerant `read_json_object` in `signal_brief` returns `{}` for a bad file, so it is not reused here.
  3. **Late re-read.** Read the file and set the two keys. Just before calling `jsonstate`'s `write_json_atomic`, which serialises and replaces in one call, re-read the target, and write only if its bytes still equal the first read. If they changed, retry once, then refuse.
     - `write_json_atomic` writes with `indent=1`, so the first write reformats `settings.local.json`. That's cosmetic.
     - A Claude Code write between that re-read and the replace (such as an "always allow" rule landing) can still be lost.
     - The race is wider than one call: brief's `_replace`, which `jsonstate` inherits, retries `os.replace` on `PermissionError` while Windows' file watcher holds the file.
     - The console only writes on a click, and the backup below covers it.
  4. **Backup.** Before writing, it saves the old file to `.state/settings.local.bak.json`.
- **What the label says.** A local `model`/`effortLevel` applies to every new Claude Code session in Signal: the sessions daemon's, terminal ones, their subagents, and the voice brain unless it overrides them (below). The row says so (`applies to every new Signal session`), and a hint says to switch the running orchestrator from the model name under the VS Code prompt box.

**Voice row.** It shows `[model ▾] [effort ▾]`.

- **The file.** The console writes `tools/audiohub/.cache/brain-choice.json` (`{model, effort}`; `.cache` is gitignored, `CACHE_DIR`). The brain reads it at connect and before each turn, checking both values against the same fixed list; an unknown value is ignored and logged. `audiohub.toml` stays the default.
- **Model** changes go through `set_model()` before the turn.
- **Effort** changes need a reconnect between turns with `resume=<session_id>` and the new `effort`, unless the `apply_flag_settings` probe (§7) shows the CLI takes `effortLevel` live. That control request is in the bundled CLI but not exposed in Python SDK 0.2.168. If the probe passes, drop the reconnect.
  - This is new work: the brain must capture the session id from the init message and pass `resume`.
  - Each reconnect costs a CLI startup (a few seconds, MCP servers included) on that turn.
- **What the Voice view says:** `applies on your next request`.

**Leak guard.** Voice loads `local` settings, so the orchestrator's local keys would reach it. The brain always passes an explicit `model` and `effort`: `brain.model` defaults to `sonnet`, and a new `brain.effort` to `low`. There's no `env.CLAUDE_CODE_EFFORT_LEVEL` anywhere. The docs put that variable, `--effort` and `/effort` in one tier without saying which of them wins, so it may outrank voice's `--effort`.

**Security README update.** "The console never acts by itself" gets one exception: on the owner's click, the console server writes two allowlisted settings keys and voice's `brain-choice.json`. Nothing else, and never on a message or agent request.

## 2. Active tasks page

### 2.1 Data

**New `packages/tasks` (`signal_tasks`)** holds the schema, validation and pruning.

- It takes the state path as an argument; nothing is hard-coded.
- For locking and atomic writes it reuses one shared writer, not a third copy.
  - Extract `signal_brief.store` (`state_lock`, `write_json_atomic`) into a small `packages/jsonstate`.
  - The extraction reworks `state_lock(BriefPaths)` into a path-based `state_lock(lock_path)`, and `BriefLogError` into a neutral `StateFileError`, which covers read, write and lock failures; brief wraps it.
  - Move usage `store.py` onto it when that's next touched.
- The console passes `tools/console/.state/tasks.json`:

```json
{"updated_at": "<ISO>", "tasks": [
  {"id": "brief-p2", "name": "Brief phase 2", "pct": 60, "status": "review",
   "next": "fresh reviewer on the hub diff", "you": "", "updated_at": "<ISO>"}]}
```

- **Status:** `status` is `review` (1), `building` (2), `needs_you` (3), `queued` (4) or `done` (5), the board's status numbers.
- **`you`:** what the owner must do; required for `needs_you`.
- **Pruning:** done tasks are pruned after 24 h, keeping the newest 20.

**CLI** (run by the orchestrator from the repo root):
- `console tasks set ID --name N --pct P --status S --next T [--you T]` upserts and validates the fields (pct 0-100, id pattern, lengths).
- `console tasks done ID`, `console tasks rm ID` and `console tasks show`.

**AGENTS.md §3** gains one line: the orchestrator runs `tasks set` when it spawns, sends to review, gets PASS, or needs the owner. Hooks can't do it, since `SubagentStart` carries only an id and a type.

**Server:** it polls the mtimes of `tasks.json` and `tools/usage/.state/usage.json` at 1 Hz and pushes a `tasks` SSE event. Reads follow the usage README's reader rules.

### 2.2 Page

A new `tasks` view, `Ctrl+5`, styled like the other views.

- **Header:** `TASKS   4 active · 1 needs you · overall 58%`, and on the right `5h 42% (resets 14:10) · wk 18% · agents 5 · as of 2 min ago`.
  - A window that's null, or whose `resets_at` has passed, shows `5h --`.
- **Rows** are ordered like the grid: by % done (highest first), then queued, then done.
  - One task per row: `[1 review]  Brief phase 2  60%`, with the next step underneath.
  - A `needs_you` row puts `YOU: <text>` in bold.
  - Status is always the number plus the word, never colour alone. Colour comes from tokens only.
- **Grouped rows:** `Queued: 6 tasks, none started` and `Done today: 3`.
- **Empty:** `No tasks reported. The orchestrator writes them with console tasks set.`

### 2.3 Whiteboard from the same file

A new `board_tasks_show` MCP tool and `whiteboard tasks show` CLI draw the grid from `tasks.json` and `usage.json`, using the `whiteboard-task-grid` memory's layout coded once. No save is loaded, so there's no stale snapshot or ghost ink.

### 2.4 Usage nulls

`five_hour`/`seven_day` are `null` while `active_subagents` (from hooks) is live. That suggests the VS Code panel doesn't run `statusLine` (**untested**; the vs-code docs don't list status lines), and hook inputs carry no rate limits. In order:

1. **Probe first:** a status line that only touches a file, in the panel. If it runs, the nulls are a data bug, not a missing source.
2. **VS Code terminal mode** (`claudeCode.useTerminal`) runs the real TUI, so its status line should run (**untested**). It trades away the panel UI.
3. **Voice SDK `RateLimitEvent`** (`rate_limit_type`, `utilization` 0-1, `resets_at`) is emitted only "when rate limit state changes" and only while voice runs. It's too sparse to rely on.

## 3. MCP servers always there

### 3.1 Facts

- **Approval isn't the problem.** `enableAllProjectMcpServers: true` is already in `.claude/settings.local.json`, and SDK sessions load `.mcp.json` servers without asking (mcp).
- **No stdio auto-reconnect.** "Stdio servers are local processes, and Claude Code doesn't reconnect them automatically" (mcp). `/mcp reconnect all` retries failed ones.
- **`.mcp.json` edits mid-session:** the docs say nothing. Observed: brief and sleepmode stayed absent until a reconnect, and `/clear` keeps servers.
- **Voice** loads `.mcp.json` through the `project` setting source, plus its inline `hand_off` server. That set is fixed for the life of the brain's `ClaudeSDKClient`. The SDK has `get_mcp_status()` and `reconnect_mcp_server(name)`.

### 3.2 Recommendation

1. **Re-read on failure, every daemon-backed server.**
   - On a 403 or refused connection, re-read the daemon's address and token and retry once: 02d6242's pattern.
   - Whiteboard has it. Audit sessions, browser, sleepmode and audiohub `notify`.
   - Servers started before the fix still need one new session. After that, a daemon restart costs nothing.
2. **Voice self-heal, partial.**
   - Before each turn, the brain reconnects any server `get_mcp_status()` reports as `failed`.
   - If `.mcp.json`'s mtime changed, it reconnects between turns with `resume` (the same path as §1.3).
   - It can't detect a server that is connected but stale (an old token, old code): status reports it as connected. Item 1 covers stale tokens. Old code needs a hub restart.
3. **New servers wait for the next session.** For the orchestrator, that's its next session (handoffs are frequent). For voice, item 2 handles it.

**Later, maybe: a stdio shim** that keeps the pipe while respawning the real server (on exit or code change). Its risks:
- it live-loads code that hasn't passed review into running sessions;
- it has to pass through each server's capabilities, instructions and server-initiated requests correctly;
- it's one more process that every tool call depends on.

## 4. Truthful busy status

Today `busy` runs from a console send to the next Stop, so turns started in VS Code, and background agents, never show.

**Hooks:** new `signal_console.hooks.turn`, registered for `UserPromptSubmit`, `Stop`, `StopFailure` and `Notification` (matcher `idle_prompt`). It only reports from the claimed session, using the same socket check as `stop.py`.

**Hook output contract** (both new hooks, `session` and `turn`, the same as `stop.py`):
- They are registered `async: true`.
- They never write to stdout, always exit 0, and log failures to `.state/hook.log`.
- Why it matters:
  - plain stdout from `UserPromptSubmit`, `SessionStart` and `PostModelSwitch` becomes context Claude sees;
  - exit 2 on a synchronous `UserPromptSubmit` blocks the prompt;
  - an async hook's JSON `additionalContext` and `systemMessage` still reach Claude on the next turn (hooks).
- **Start:** `UserPromptSubmit` POSTs `/api/hook/turn {phase: "start", session_id, at}`. The docs say it "also fires on turns Claude Code starts on its own", so background-agent completions and inbox turns start a turn too.
- **End:** `Stop` sends `phase: "end"` (plus `effort.level` and `background_tasks`), and the existing reply post moves into it.
- **API errors:** Stop "does not run if the stoppage occurred due to a user interrupt", and "API errors fire StopFailure instead" (hooks). So `StopFailure` also sends `end`.
- **Idle:** `Notification` `idle_prompt` also sends `end`, but only when the open turn's start is at least about 60 s old.
  - The docs say it fires "about 60 seconds after Claude finishes responding, and only if you haven't typed since and no background agent ... is still running".
  - An inbox turn isn't typing, so without the age check a late `idle_prompt` from the previous turn could end it.
- **Ordering:** `at` is stamped when the hook process starts, and async hooks can land out of order. On a short turn, `start.at` can therefore be later than `end.at`.
  - The server ignores a `start` older than the last `end`.
  - It treats a `start` within about 2 s after the last `end` as part of that finished turn. This fails safe toward `idle`, and the next hook corrects it.

**Interrupts fire nothing.** Any hook from the session (start, end, the usage `SubagentStart`/`Stop` updates) refreshes `last_activity`. After 10 min of `working` with no activity, the state turns `stale`.

**Agents:** the count is `usage.json` `sessions[<claimed id>].agents` with `seen_at` under 2 h.
- It can count phantoms: agents Esc'd or killed without a `SubagentStop`.
- Stop's `background_tasks` array is a second count, checked at each turn end. When the two disagree, the console shows the lower one with a `?`. Probe both.

| State | When | Shows |
|---|---|---|
| working | start seen, no end | `working 0:42` (+ ` · 5 agents`) |
| agents | no turn, agents > 0 | `waiting on 5 agents` (hollow dot, slow pulse) |
| idle | no turn, no agents | `idle` |
| stale | working, no hook activity for 10 min | `no word from Claude for 12 min (interrupted?)` |
| unknown | no hook since server start | `status unknown until Claude's next turn` |

The console stops setting busy on send. It shows `sent` until the start hook arrives.

## 5. Whiteboard buttons

Actions keep today's channel. The row shows `sending`, `sent`, `working` and `done`, and the detail ("nothing moved", "night view is on") is the orchestrator's reply line in chat. Nothing parses replies.

### 5.1 Realign

- **The button.** `Realign board` in the Boards header, action `board.realign`. The orchestrator runs `board_realign`: a ~1 s marker flash that keeps items, and changes nothing if nothing moved.
- **If it fails** (markers unseen), the orchestrator says so and offers full `board_calibrate`. There's no auto-escalation.
- **Confirms.** Realign has none. `Full calibrate` (`board.calibrate`) goes through the existing `ConfirmLine`: `Flash calibration markers on the projector? y/n`.
- **Night view.** Both buttons are disabled while the console's board status shows the night view: `Night view is on; calibration would light the room`. A 409 that still comes back reaches chat as the orchestrator's reply.

### 5.2 Update on live boards

- **The `refresher` field.** `meta.json` gets an optional `refresher` taken from a fixed enum (`tasks`, `todo`), never a command. `board_save` takes `refresher=`, and the existing `agent-task-grid` save gets `tasks`.
- **The action.** `board.update {name}` validates like `board.load` in `messages.py`: the name must be a current save, and that save must have a refresher. Otherwise it raises `RequestError`.
- **What the orchestrator runs:**
  - for `tasks`, `board_tasks_show` (§2.3), never `board_load`;
  - for `todo`, `whiteboard todo sync`, then `board_todo_show`.
- **Where the button shows:** the Boards list shows `Update` only on rows with a refresher. The to-do view, which isn't a save, gets the same button in its header.

## 6. Stopping a hub started elsewhere

- **The console's flow stays as it is.** `console hub start`, its `.state/hub.json` record, the start guard, the watcher's `hub.log` tail keyed on that record, and `startedBy` are all unchanged.
- **One addition: the hub writes its own record, for Stop only.** `audiohub run` writes `tools/audiohub/.cache/hub.json` (owner-only, atomic) with `pid`, `create_time` and `started_by`.
  - It writes the record only after its kernel IPC port is bound. A second hub that fails to bind never touches it.
  - On a clean exit it removes the record only if the pid in it is its own, the same way `remove_token_file(path, token)` checks its token.
  - The write and the removal go in `Conversation`, right after `_start_server` and inside its `AsyncExitStack` (`loop/conversation/conversation.py:141-153`), so `run --phone` gets them too.
  - The IPC token file already follows the bind-first rule: `KernelServer.start()` binds first, then writes the token, and closes the listener if that write fails (`kernel/ipc/server.py:91-98`).
- **Status is unchanged.** Running means the hub's port is listening. The console's record decides whether it shows `console` or `external` (`server/watcher.py:128-134`, `cli/commands.py:52-56`). `VoiceView.tsx:45-61` already shows Stop for an external hub.
- **Stop.**
  - If `find_console_hub` returns a process, Stop kills that tree, as today.
  - Whenever `find_console_hub` returns None, Stop falls back to the hub's own record. That includes a stale console record left by a crashed hub: today `stop_hub` unlinks it and kills nothing (`hub/process.py:103-127`), so a crashed console hub followed by a terminal hub would need two Stops.
  - The hub's record is checked with `find_recorded_process(pid, create_time)` plus `_runs_from_audiohub`, both behind a public `find_hub()` in `hub/process.py`. The recorded pid is the base interpreter, so `_runs_from_audiohub` checks for the venv's `audiohub.exe` on the command line.
  - A verified record is killed with the existing tree kill.
  - With nothing to stop, the CLI's `"The console's voice hub isn't running."` (`cli/commands.py:45`) becomes `"No voice hub the console can stop is running."`
- **Readers never delete records.** A stale record (dead pid, reused pid, not the hub) just reads as not running, and the next hub overwrites it.
- **Out of scope:** the existing check-then-spawn race between two console Starts. It's low-impact: the second hub fails to bind, so its record is never written.

## 7. Phases and tests

Tests stay small (AGENTS §6), and several cases share one parametrize.

1. **Status and hub:** §4 hooks and states; §6 hub record.
   - Tests: turn ordering (start → end, start → StopFailure, a late `start` after `end` ignored, a start within 2 s of an end folded into it, `idle_prompt` ignored on a turn under 60 s old, stale after silence).
   - Hub record:
     - the record is written only after the bind; a clean exit removes it only when the pid in it is the hub's own.
     - Stop, parametrized:
       - with a live console hub, it kills that tree;
       - with no console record, or a stale one (the crashed-console-hub case), it kills the tree from the hub's verified record in one Stop;
       - a reused pid or a non-hub exe in the hub's record kills nothing and leaves the record in place.
   - Hook contract, parametrized over each hook entry point (`turn` for each event): with bad input or no server, stdout stays empty and it returns 0.
2. **Tasks:**
   - Build: `packages/jsonstate` extraction, `packages/tasks`, `console tasks`, the AGENTS.md line, the Tasks view, `board_tasks_show`, `refresher`, Update and Realign.
   - Tests: `tasks set` validation (bad pct, status, id; `needs_you` without `you`) and pruning.
   - Refresher enum: an unknown value is refused on save and read, and `board.update` is refused for a save with no refresher.
3. **Models:**
   - Build: the session-model hook and lookup, the settings writer, `brain-choice.json`, the brain's resume reconnect, explicit voice model and effort, the README security update.
   - Settings writer, parametrized:
     - an allowlisted key and value is written;
     - "use my user settings" removes the key;
     - a non-allowlisted key or value, a missing, malformed or non-object file, and a file that changes before replace are all refused, leaving the file byte-identical;
     - other keys survive a write.
   - Session models: pruned to 20, updated by `PostModelSwitch`, looked up by the claimed id. The same hook-contract test covers `session`.
   - Brain: an unknown value in `brain-choice.json` is ignored. An effort change takes the resume reconnect, and a model change calls `set_model` with no reconnect.
4. **MCP:**
   - Build: the re-read audit across servers, voice self-heal.
   - Tests: one regression test per server that gains re-read; voice reconnects only `failed` servers.

Probes, about 10 minutes each:
- whether the panel runs `statusLine`;
- `background_tasks` against the usage count after an Esc'd agent;
- whether `Notification` `idle_prompt` fires after an Esc interrupt, and whether it fires at all in the VS Code panel;
- whether the CLI's `apply_flag_settings` control request with `effortLevel` changes voice's effort live.

## 8. Decided (the owner, 2026-10-20)

1. **Scope of a model or effort pick:** Signal only, in `.claude/settings.local.json`. It applies to every new Signal session, including the orchestrator, the sessions daemon, terminals and subagents.
2. **Voice defaults:** Sonnet at low effort.
3. **Tool names stay as they are.** No aggregator, so a new MCP server shows up in the next session.
4. **Tasks:** the orchestrator updates `tasks.json` itself on every state change.
5. **Update and Realign** go through the orchestrator, like today's buttons.
6. **Full calibrate** needs a confirm click. Realign doesn't.
