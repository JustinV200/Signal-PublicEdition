"""Claude Code session hook: record which model each Signal session runs, for the model strip.

Run as `<console venv>\\Scripts\\python.exe -m signal_console.hooks.session`,
registered async for SessionStart (its `model`, which is sometimes left out)
and PostModelSwitch (its `to_model`). It writes `{session_id: {model, at}}`
into .state/session-models.json for every session, claimed or not:
SessionStart fires before `console claim` runs, so the hook can't tell which
session the console will follow. The server looks the claimed one up later.

Like the turn hook it never writes to stdout (for both events that would
become context Claude sees) and always exits 0; failures go to .state/hook.log.
"""

import json
import sys
import time
from pathlib import Path

from signal_console.hooks.hook_log import log_hook_failure
from signal_console.models import record_session_model
from signal_console.paths import SESSION_MODELS_FILE, STATE_DIR

MAX_STDIN_BYTES = 1024 * 1024
# Which input field names the model, per event.
MODEL_FIELDS = {"SessionStart": "model", "PostModelSwitch": "to_model"}


def record_from_hook(raw_input: bytes, state_dir: Path, at: float) -> bool:
    """Record this event's model for its session.

    Args:
        raw_input: The hook's JSON input (hook_event_name, session_id, model or to_model).
        state_dir: The console's .state folder.
        at: Epoch seconds when the hook process started.

    Returns:
        True if it was recorded; False for another event, a missing or odd
        model or session id, or a report older than the one on file.

    Raises:
        ValueError: The input isn't a JSON object.
        signal_jsonstate.StateFileError: The file couldn't be locked, read or written.
    """
    payload = json.loads(raw_input)
    if not isinstance(payload, dict):
        raise ValueError("the hook input isn't a JSON object")
    field = MODEL_FIELDS.get(payload.get("hook_event_name"))
    if field is None:
        return False
    path = state_dir / SESSION_MODELS_FILE
    return record_session_model(path, payload.get("session_id"), payload.get(field), at)


def main() -> int:
    """Hook entry point. Always returns 0 and never prints."""
    at = time.time()  # first: async hooks can land out of order, so the stamp orders them
    try:
        record_from_hook(sys.stdin.buffer.read(MAX_STDIN_BYTES), STATE_DIR, at)
    except Exception as error:  # noqa: BLE001 - a hook must never fail the session
        log_hook_failure(STATE_DIR, error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
