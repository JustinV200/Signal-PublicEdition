# mail_digest.memory

What the runner remembers between runs, and the lock that keeps runs from overlapping. Only the runner touches `.state/`; the model can't reach it, and none of it is shown to the model.

## Public API (`from mail_digest.memory import ...`)

- `DigestState(searched_until, announced, failures, needs_review, was_reset, pending)`, `load_state(path, max_keys, keep_copy=True)`, `save_state(path, state)` (atomic). A missing file starts fresh. A corrupt one is copied to `state.json.corrupt` (unless `keep_copy` is False, as in a dry run) and starts fresh with `was_reset` set, which isn't saved; the runner announces the reset that run. One that's there but can't be read raises `OSError`: the file and its `needs_review` flags are left as they are, and the run stops and says out loud that it can't read its state. Keys that don't match `KEY_PATTERN` are dropped on load. `needs_review` lists the `life/` files with an edit the KB guard couldn't check, which the runner announces every run until they've been reviewed. The runner flags every file a run may edit before claude starts and clears them after the guard, so a run stopped in between leaves them flagged. `pending` (`Pending(key, sentence, first_seen)`) holds announcements the hub didn't take, for `steps/outcome.py` to retry; malformed entries are dropped on load.
- `search_windows(state, aliases, now, Lookback(first_run_s, max_s, overlap_s))` returns a `Window(after, before, skipped_since)` per alias. A known account starts `overlap_s` before its `searched_until`, and no window reaches back past `max_s`. `skipped_since` is set when that cap cut mail out.
- `advance_windows(state, windows, completed)`: completed accounts move to their window's end and `failures` resets. `record_failure(state)`: one more consecutive failure, windows untouched.
- `remember_announced(state, keys, now, KeyRetention(keep_s, max_keys))`: stores keys first spoken at `now`, forgets ones older than `keep_s` and keeps the newest `max_keys`. `is_valid_key(key)` is the strict key check.
- `run_lock(path)`: a context manager holding a Windows byte-range lock (`msvcrt.locking`). Raises `LockHeldError` at once if another run holds it. The OS releases it if the process dies. `is_locked(path)` checks without holding it.

## Files

`state.py`, `lock.py`.

## Dependencies

Standard library only (`msvcrt` makes `lock.py` Windows-only, like the rest of the job).
