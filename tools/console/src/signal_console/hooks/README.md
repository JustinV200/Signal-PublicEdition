# hooks

Claude Code hook scripts, run as modules by the console venv's `python.exe`.

- `turn.py`: the turn hook, registered async for `UserPromptSubmit`, `Stop`, `StopFailure` and `Notification` (matcher `idle_prompt`). If this is the claimed session, it POSTs `{phase, session_id, at}` to `/api/hook/turn`, with `at` stamped when the hook process started. Stop's report adds `background_tasks` (a count), `effort` (the input's `effort.level`, else `$CLAUDE_EFFORT`) and `text` (`last_assistant_message`). It never prints (plain stdout from `UserPromptSubmit` would become context Claude sees) and always exits 0; failures go to `.state/hook.log`. Setup registers it (the console's entry in `tools/setup/src/signal_setup/data/tools.json`).
- `session.py`: the session hook, registered async for `SessionStart` (`model`) and `PostModelSwitch` (`to_model`). For every session, claimed or not, it records `{session_id: {model, at}}` in `.state/session-models.json` (`models.record_session_model`). Same contract: no stdout, exit 0, failures to `.state/hook.log`.
- `hook_log.py`: `log_hook_failure(state_dir, error)`, both hooks' one outlet.
- `reply.py`: `fit_reply(fields, text)` cuts the reply by encoded size so the whole body fits the server's 64 KB limit.

Depends on `local_api`, `models`, `orchestrator` and `paths`. It deliberately avoids `aiohttp`, so it starts fast.
