# brief

Puts the owner's catch-up brief (`packages/brief`, `signal_brief`) in front of Claude sessions and the owner: the `brief` MCP server, the `brief` CLI and the Claude Code `UserPromptSubmit` hook. Design: `refdocs/research/brief-me.md`, phase 1. Python 3.12, uv; depends on `mcp`, `signal_brief` and `signal_untrusted`.

State lives in `.state/` (gitignored): the brief's files (see `packages/brief/README.md`) plus `hook.log`.

## Trust

Every model-bound output is one fixed trusted line (`wording.py`) plus at most one `<untrusted_brief_content>` frame with `<` escaped (`signal_untrusted`). Titles, details and notes only ever travel inside the frame. `brief_undo` puts the undo action outside the frame and the title inside; Claude states the action and waits for the owner's yes.

## MCP server (`brief mcp`, server name `brief`)

`brief_me(kind="general")`, `brief_ack(delivery_id)`, `brief_log(kind, title, key="", detail="", undo=None, priority="normal", untrusted=False)`, `brief_resolve(key_or_ref)`, `brief_get(ref)`, `brief_undo(ref)`, `away_on(until="", note="")`, `away_off()`, `away_status()`.

- Each `brief_me` call is a delivery. It is acked only by the prompt hook, on the owner's next present prompt, by the refs Claude passed on.
- `brief_ack` acks nothing in a session and tells Claude to have the owner say "got it"; with `SIGNAL_BRIEF_SURFACE=managed` (the sessions daemon sets it) it refuses.
- Entries a session logs get `source` "session" (or "managed").

## Prompt hook (`brief_tool.hooks.prompt`)

Per prompt, always exiting 0:

1. Away or asleep: add the away rules.
2. Stop if managed, a subagent's prompt (`agent_id`), a tag-wrapped turn (starts with `<`), or the last input came over 5 s before the hook.
3. Ack this session's unseen deliveries by the ref rule, found by id among its own hook injections and `mcp__brief__brief_me` results in `transcript_path`, counting only assistant text after each.
4. On `full`, inject the refs and titles (at most 2,000 chars) once per session and due brief, recorded as a delivery with the session id; on `one_liner`, the one-liner. A due brief never expires: it stays due until a delivery of it is acked. A session that already got it gets the one-liner instead after a 6 h gap, if there's an entry the owner hasn't been briefed on (once per gap).

`hook.log` gets the session id, decision and timing, never prompt text.

Caveat: input is system-wide, so synthetic input counts, and so does an untagged peer message that lands within 5 s of the owner typing elsewhere.

## CLI

```
brief show [--plain]             # markdown on a terminal, framed when piped (--plain: never framed, for the owner only); never acks
brief away on [--until sunday] [--note "at the cabin"]
brief away off
brief away status
```

There's no CLI ack: only a surface that knows the owner saw a brief may ack it.

## Setup

1. `cd tools/brief && uv sync`.
2. `.mcp.json` gets `"brief": {"command": "uv", "args": ["run", "--env-file", ".env", "--project", "tools/brief", "--frozen", "brief", "mcp"]}`. It must not set `SIGNAL_BRIEF_SURFACE`.
3. `.claude/settings.local.json` gets the hook (exec form; `-I` keeps a stray `json.py` in the cwd off `sys.path`):
   ```json
   "UserPromptSubmit": [
     {
       "hooks": [
         {
           "type": "command",
           "command": "C:/src/Signal/tools/brief/.venv/Scripts/python.exe",
           "args": ["-I", "-m", "brief_tool.hooks.prompt"],
           "timeout": 10
         }
       ]
     }
   ]
   ```

## Layout

`src/brief_tool/`: `cli.py`, `surface.py` (`SIGNAL_BRIEF_SURFACE`), `wording.py` (trusted text), `mcp_server/` and `hooks/`, each with a README.

## Tests

`uv run --frozen --no-sync pytest`: the hook's presence gating (with the 5 s caveat), once-per-session injection, acks from transcripts (only from `brief_me`'s own results), away rules and a log free of prompt text; the MCP tools' framing, undo and managed refusal.
