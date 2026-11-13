"""The state file's safe read-merge-write, shared by the status line and the hook.

Several Claude Code sessions run the status line and hooks at once, so every
change goes through update_state: it takes a lock file (bounded wait), reads
the file, applies the change and writes the result back atomically (a temp
file, then os.replace). Readers such as the whiteboard need no lock, because
they only ever see a whole file.
"""

import contextlib
import json
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from usage.times import to_iso

State = dict[str, Any]
# A change gets the current state and the time, and returns the new state.
StateChange = Callable[[State, datetime], State]

# The default lock wait, the status line's: it runs again within seconds, so
# giving up on one update costs little.
LOCK_WAIT_S = 1.0
LOCK_POLL_S = 0.01
# A writer holds the lock for milliseconds. One older than this was left by a
# process that died holding it (Claude Code kills a status line still running
# when the next update starts), so it's broken.
STALE_LOCK_S = 2.0
# The hook's lock wait. A start or stop that gives up is lost (a lost stop
# leaves a phantom agent for 2 h), so it waits past STALE_LOCK_S for a dead
# writer's lock to be broken, and stays within the hook's 5 s timeout.
HOOK_LOCK_WAIT_S = 3.0
REPLACE_ATTEMPTS = 5
REPLACE_RETRY_S = 0.02


class StateLockTimeoutError(TimeoutError):
    """A live writer held the state lock for longer than the caller would wait."""


def empty_state() -> State:
    """The state before anything is known: no usage windows, no subagents."""
    return {
        "five_hour": None,
        "seven_day": None,
        "active_subagents": 0,
        "sessions": {},
        "updated_at": None,
    }


def read_state(state_file: Path) -> State:
    """The state from the file, or an empty state if there's no file yet.

    Writes are atomic, so a malformed file can only come from a hand edit. It
    reads as empty, and the next write replaces it rather than every write
    failing until someone fixes it.

    Raises:
        OSError: The file exists but couldn't be read.
    """
    try:
        payload = json.loads(state_file.read_bytes())
    except (FileNotFoundError, ValueError):
        return empty_state()
    return payload if isinstance(payload, dict) else empty_state()


def update_state(
    state_file: Path, change: StateChange, now: datetime, lock_wait_s: float = LOCK_WAIT_S
) -> State:
    """Apply `change` to the state file under its lock, stamp updated_at and write it atomically.

    A change that leaves the state as it was (updated_at aside) writes nothing.

    Args:
        state_file: The state file; its folder is created if missing.
        change: Builds the new state from the current one and `now`.
        now: The time of this update (aware).
        lock_wait_s: How long to wait for another writer's lock.

    Returns:
        The state as written, or as read when nothing changed.

    Raises:
        StateLockTimeoutError: Another writer held the lock past `lock_wait_s`.
        OSError: The file couldn't be read or written.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = state_file.with_name(f"{state_file.name}.lock")
    _acquire_lock(lock_file, lock_wait_s)
    try:
        known = read_state(state_file)
        state = change(known, now)
        # A no-op (an idle session re-sending its cached values) isn't written,
        # so updated_at stays the time of the last real change and readers
        # aren't made to race os.replace for nothing.
        if known.get("updated_at") and _without_stamp(state) == _without_stamp(known):
            return known
        state["updated_at"] = to_iso(now)
        _write_atomic(
            state_file, state, max(REPLACE_ATTEMPTS, round(lock_wait_s / REPLACE_RETRY_S / 10))
        )
    finally:
        # shortcut: breaking stale locks can let two writers in at once, and the
        # later write then drops the earlier one's change. That needs a writer
        # stalled past STALE_LOCK_S (its lock is broken, and this unlink then
        # removes the next writer's), or two waiters breaking the same stale lock
        # (the second's unlink removes the lock the first just took). Both need a
        # writer that died or hung for seconds; move to an OS lock
        # (msvcrt.locking) if lost updates show up.
        lock_file.unlink(missing_ok=True)
    return state


def _without_stamp(state: State) -> State:
    return {**state, "updated_at": None}


def _acquire_lock(lock_file: Path, wait_s: float) -> None:
    """Create `lock_file` exclusively, waiting up to `wait_s` and breaking a stale one.

    Raises:
        StateLockTimeoutError: The lock was still held after `wait_s`.
    """
    deadline = time.monotonic() + wait_s
    while True:
        try:
            os.close(os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return
        except (FileExistsError, PermissionError):
            pass  # Held (Windows says PermissionError while it's being deleted).
        if _is_stale(lock_file):
            # A failed removal means another writer broke it first, or it can't
            # be deleted (read-only, or delete pending on Windows). Either way,
            # fall through to the deadline check so the wait stays bounded.
            with contextlib.suppress(OSError):
                lock_file.unlink()
        if time.monotonic() >= deadline:
            raise StateLockTimeoutError(f"{lock_file} held for over {wait_s} s")
        time.sleep(LOCK_POLL_S)


def _is_stale(lock_file: Path) -> bool:
    try:
        return time.time() - lock_file.stat().st_mtime > STALE_LOCK_S
    except OSError:
        return False  # Released meanwhile; the next try takes it.


def _write_atomic(state_file: Path, state: State, replace_attempts: int) -> None:
    # Per-process temp name: a broken lock can let two writers in at once (see
    # the shortcut in update_state), and they mustn't share one temp file.
    temp = state_file.with_name(f"{state_file.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        for attempt in range(replace_attempts):
            try:
                os.replace(temp, state_file)
                return
            except PermissionError:
                # Windows won't replace a file another process (a reader) has open.
                if attempt == replace_attempts - 1:
                    raise
                time.sleep(REPLACE_RETRY_S)
    except OSError:
        # No later write reuses this per-process name, so clear it here.
        temp.unlink(missing_ok=True)
        raise
