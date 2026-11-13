"""`.state/session-models.json`: which model each recent Claude Code session is running.

The session hook (hooks/session.py) records `{session_id: {model, at}}` for
every Signal session at SessionStart and PostModelSwitch, since SessionStart
fires before `console claim` and so can't know which session is the claimed
one. The server looks the claimed session up by the id its turn hooks report.
Sessions start concurrently, so writes hold the jsonstate lock. A value that
isn't a short model id is never written or shown. Only the stdlib and
signal_jsonstate (itself stdlib only), so the hook starts fast.
"""

import re
from pathlib import Path
from typing import Any, TypeGuard

from signal_jsonstate import StateFileError, read_json_object, state_lock, write_json_atomic

# A short model id or alias, e.g. "claude-opus-5-5" or "opus[1m]".
MODEL_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9.\-\[\]]{0,63}")
# Claude Code session ids are UUIDs; anything much longer isn't one.
MAX_SESSION_ID_CHARS = 128
MAX_SESSIONS = 20


def is_model_id(value: object) -> TypeGuard[str]:
    """Whether `value` is a string shaped like a model id (the only kind shown or stored)."""
    return isinstance(value, str) and MODEL_ID_PATTERN.fullmatch(value) is not None


def record_session_model(path: Path, session_id: object, model: object, at: float) -> bool:
    """Note that `session_id` runs `model` as of `at`, keeping the newest MAX_SESSIONS.

    An entry stamped later than `at` is kept: async hooks can land out of
    order, so a late SessionStart mustn't undo a PostModelSwitch.

    Args:
        path: session-models.json; its lock is the same name plus `.lock`.
        session_id: The hook input's session_id.
        model: The hook input's model (SessionStart) or to_model (PostModelSwitch).
        at: Epoch seconds when the hook process started.

    Returns:
        True if it was written; False for a bad id or model, or an older report.

    Raises:
        StateFileError: The file couldn't be locked, read or written.
    """
    if not _is_session_id(session_id) or not is_model_id(model):
        return False
    with state_lock(path.with_name(f"{path.name}.lock")):
        sessions = _valid_entries(read_json_object(path))
        if sessions.get(session_id, {}).get("at", -1.0) > at:
            return False
        sessions[session_id] = {"model": model, "at": at}
        newest = sorted(sessions.items(), key=lambda item: item[1]["at"], reverse=True)
        write_json_atomic(path, dict(newest[:MAX_SESSIONS]))
    return True


def read_session_model(path: Path, session_id: str) -> str | None:
    """The model recorded for `session_id`, or None if unknown, unreadable or not a model id."""
    try:
        entry = read_json_object(path).get(session_id)
    except StateFileError:
        return None
    model = entry.get("model") if isinstance(entry, dict) else None
    return model if is_model_id(model) else None


def _is_session_id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and 0 < len(value) <= MAX_SESSION_ID_CHARS


def _valid_entries(sessions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # A hand-edited entry without a numeric stamp can't be ordered, so it's dropped.
    return {
        session_id: entry
        for session_id, entry in sessions.items()
        if isinstance(entry, dict)
        and isinstance(entry.get("at"), int | float)
        and not isinstance(entry.get("at"), bool)
    }
