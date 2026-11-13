# brief_tool.hooks

The Claude Code `UserPromptSubmit` hook. Entry point: `python -I -m brief_tool.hooks.prompt`.

- `prompt.py`: reads the hook input, applies the four steps (away rules, presence gate, acks, injection) and prints `hookSpecificOutput.additionalContext`. `handle_prompt(event, HookRun)` is the testable core; `skip_reason` is the gate.
- `session_acks.py`: `ack_session_deliveries` acks this session's unseen deliveries by `signal_brief.relayed_through`.
- `transcript.py`: `replies_after_deliveries` finds deliveries in `transcript_path` (hook attachments for this session's ids, `mcp__brief__brief_me` tool results for `brief_me` ids) and returns the assistant text after each. It streams the file and only parses lines that can matter.
- `injection.py`: `brief_injection` runs `on_interaction` and builds the full brief (once per session and due brief, again an hour on while none of them is acked) or the one-liner. The due brief never expires; only an ack drops it. Once an ack drops it, the 6 h gap one-liner comes from `on_interaction`'s own `one_liner` offer.
- `hook_log.py`: one cleaned `key=value` line per prompt in `.state/hook.log`, never prompt text.

Depends on: `signal_brief`, `signal_untrusted`, `brief_tool.surface`, `brief_tool.wording`.
