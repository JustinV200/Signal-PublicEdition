# contextmeter

A Claude Code `PostToolUse` hook that tells each agent, subagents included, how much of its context window it has used. It backs the AGENTS.md section 4 rule (hand off at N% of your context window) with a real number. Stdlib only, Python 3.12, uv.

## What the agent sees

After a tool call, the hook may add one line next to the tool result:

- `Context: 58% used (handoff at 75%).`
- At or past the threshold: `Context: 77% used, past the 75% handoff line. Stop starting new work and hand off now, per AGENTS.md section 4.`

It stays quiet below 40%. From there it speaks once per new 10% band (40, 50, ...), and once more on crossing the threshold. If usage drops (after a compaction), it re-announces when it climbs again.

## How it works

- **Whose context.** Inside a subagent the hook input carries the session's `transcript_path` plus the subagent's `agent_id`. The subagent's own transcript is `<session transcript without .jsonl>/subagents/agent-<agent_id>.jsonl`. With no `agent_id`, it's the main agent and the session transcript is used.
- **Usage.** The newest assistant message in that transcript with non-zero usage: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`. Only the file's tail is read. The transcript is written asynchronously, so the number can lag by one turn.
- **Window.** `WINDOW_BY_MODEL_PREFIX` in `src/contextmeter/window.py`, an editable table. Transcripts never show a `[1m]` suffix, so the table is what decides; anything not listed gets 200k, and usage past the table's window is taken as a 1M window.
  - The 1M rows assume the `[1m]` model variant. If you don't run it, set `window_tokens` in `contextmeter.toml` (`setup config contextmeter`, e.g. `200000`), which replaces the table for every model; otherwise the meter under-reports and warns too late. `CONTEXTMETER_WINDOW_TOKENS` in the environment wins over the file.
- **Threshold.** Read on each run from the repo's `AGENTS.md` (`$CLAUDE_PROJECT_DIR/AGENTS.md`), from the `**N% of your context window**` line (the N may sit in setup's `<!-- setting:context-handoff-percent -->` marker). Falls back to 75.
- **State.** `.state/levels.json` (gitignored) keeps the last announced level per `<session>:<agent>`, capped at 500 entries.
- **Failures.** It always exits 0 and prints nothing on error, so it can't block a tool call. Errors (type and message only) go to `.state/errors.log`, which starts over past 64 KiB. A run takes about 70 ms.

## Setup

Pick it in setup (`setup contextmeter`). Setup runs `uv sync`, offers the window setting, and `setup wire` registers the hook in `.claude/settings.local.json` with the venv's Python for your OS (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere), run as `python -I -m contextmeter.hook`. `-I` keeps the session's cwd off `sys.path`, so a stray `json.py` there can't shadow the stdlib.

## Layout

`src/contextmeter/`: `hook.py` is the entry point; `transcript.py` finds and reads the transcript; `window.py` is the window table; `threshold.py` reads AGENTS.md; `config.py` reads `contextmeter.toml`; `announce.py` decides when and what to say; `state.py` keeps the levels file.

## Tests

`uv run --frozen --no-sync pytest` covers usage parsing from a fake subagent transcript, threshold parsing, which window wins (env, config, table), the band and threshold announce logic, the hook's output, and bad input never failing or printing.
