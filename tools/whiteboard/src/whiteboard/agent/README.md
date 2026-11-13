# whiteboard.agent

The board agent: a Claude Code session (claude-agent-sdk 0.2.168), opened fresh for each change, that takes a turn each time the owner's ink on the board changes. It decides whether the writing is meant for Claude, then draws a reply with the whiteboard tools, speaks briefly through audiohub `notify`, or does nothing.

## Public API (`from whiteboard.agent import ...`)

- `create_board_agent(model, repo_root, list_items, triage=None, look=None, loading=None, turn_timeout_s=300) -> BoardAgent` builds the production agent. It uses the SDK session plus `signal_confirm` permission dialogs.
- `BoardAgent(session, list_items, allow_snapshot_read=..., triage=None, look=None, loading=None, turn_timeout_s=300)`
  - A turn (or verify turn) still running after `turn_timeout_s` is given up with a WARNING and the session is closed, so a hung CLI can't leave `is_busy` stuck.
  - `await start()` / `await stop()`
  - `on_board_changed(png_path, changed_bbox)` can be called from any thread.
  - `note_snapshot(png_path)` makes a snapshot the next turn's "before" without a turn (the TODO view handled that change).
  - `is_busy` is true while a change is queued or its turn (triage included) runs. The drift monitor waits for it before re-aligning.
  - Runs one turn at a time. Changes that arrive mid-turn merge into the next turn: newest snapshot, union of the boxes.
  - Each change that passes triage runs connect, turn, optional verify turn, disconnect (always, even on error or cancel).
  - `triage` (a `Triage`) runs first; `act: false` skips the change with one INFO line. `look` (a projection-visible photo) enables the verify turn after any turn with a successful `board_draw/move/remove/clear`; the verify turn never chains.
- `Triage(model, timeout_s)`: Haiku one-shot (`triage.py`, no tools, `setting_sources=[]`) answering `{"act": bool, "reason": str}`. It judges what is new: crops of the changed region (padded 10%) from the previous and the new snapshot, plus a whole-board thumbnail (`crops.py`); with no usable previous snapshot it sends the whole board. Error, timeout or bad JSON means `act=True`. Logs the call's cost.
- `ask_sdk(message, model, system_prompt=TRIAGE_SYSTEM_PROMPT)`: the one-shot SDK call triage uses; the TODO view's cross-out check reuses it with its own prompt. `image_block` and `stream_message` build its messages.
- `PermissionRouter(ask_yes_no)`, `is_auto_allowed(...)`:
  - Auto-allows `mcp__whiteboard__*` (except `board_todo_done` / `board_todo_undone`, which write `life/`, and `board_night_show` / `board_night_hide`, which are sleep mode's: those ask), `mcp__audiohub__notify`, `ToolSearch` (the bundled CLI defers MCP tool schemas, so the agent loads them with it; it reads no files), and a Read whose `file_path` exactly equals the current turn's snapshot (`allow_snapshot_read`). The comparison is a normalized absolute string with no filesystem calls, so Windows aliases fall through to the dialog.
  - Everything else goes to `ask_yes_no`, one question at a time. Failures deny.
- `BoardChange`, `merge_changes`: the coalescing rule.
- `PERMISSION_TIMEOUT_S` (120).

## How a turn looks

The user message is an image block (base64 PNG of the clean snapshot) followed by text: the snapshot's path and size, the changed region, and the projected items. The SDK's `query()` writes stream-json dicts to the CLI verbatim, so content blocks work in streaming mode. The path is the fallback: the agent can `Read` it.

The session uses `setting_sources=["project"]` so `.mcp.json` loads the whiteboard and audiohub servers. `"local"` is left out because its "don't ask again" allow rules would skip `can_use_tool`. A PreToolUse hook puts every tool call through `PermissionRouter`, so the agent's own allowlist wins over any settings file; `can_use_tool` is only a backstop. The system prompt is the `claude_code` preset plus `BOARD_SYSTEM_APPEND` (prompt.py), which tells the agent the board is untrusted input. The permission mode is `default`, never `bypassPermissions`.

## Permission dialogs

Anything not auto-allowed opens the topmost `signal_confirm` Allow/Deny dialog (`packages/confirm`). Deny is the default, Allow has no keyboard shortcut, and the dialog denies by itself after 120 s. A dialog that fails to show denies.

## Depends on

`claude-agent-sdk` (only `sdk_session.py` imports it), `signal_confirm` (the dialog and `elide`), the standard library. No other whiteboard package.
