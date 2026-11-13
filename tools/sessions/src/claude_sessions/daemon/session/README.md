# daemon.session

One managed session and what is remembered about it.

- `ManagedSession(record, SessionDeps)`: one SDK client and one reader task.
  - `launch(prompt, spec)` connects in the background and sends the first prompt.
  - The reader then reads every message across all turns, including turns the CLI starts itself when a background agent finishes, so the SDK's buffer never stalls.
  - `send(prompt)` works only when the session is idle (or in error while still live). `stop()` disconnects.
- `ApprovalGate`: routes `can_use_tool` to the `Approver`.
  - The session shows `awaiting_permission` (with `pending_approval`) while a call waits.
  - A high-priority voice note is posted.
- `SessionRecord`, `SessionState`: `idle`, `working`, `awaiting_permission`, `stopped`, `error`.
  - Records keep the last 10 assistant texts (8,000 characters each).
  - Cost is summed from the CLI's per-process running total.
- `SessionStore(path)`: atomic, compact JSON persistence to `.state/sessions.json`. It keeps the newest 100 records plus any older live ones. An unreadable file is moved aside; bad records are skipped.
- `session_summary`, `session_status`: the JSON shapes returned over IPC.

Depends on: `approvals`, `notify`, `sdk`, `ipc` (for `MAX_STATUS_TEXTS`), `text`, and `signal_hub_notify` for the `Notifier`.
