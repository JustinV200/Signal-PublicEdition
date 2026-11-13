# signal_brief.presence

- `presence.json` (`presence_file.py`): `last_human_at`, the due full brief (`DueBrief`: kind, `marked_at`, reason) and the morning rule's day. `mark_due_locked` and `drop_due_locked` for callers holding the lock; the drop only happens for a delivery given at or after the brief was marked due.
- `idle_ms()` (`idle.py`): milliseconds since the last keyboard or mouse input anywhere, from `GetLastInputInfo` and `GetTickCount` mod 2^32. System-wide, and synthetic input counts.

Depends on: `store`, `times`, `paths`.
