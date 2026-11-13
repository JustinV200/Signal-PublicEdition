"""Claude Code SubagentStart / SubagentStop hook: keep each session's set of active subagents.

Run as `<tools/usage venv>/Scripts/python.exe -I -m usage.hook` for both
events; -I keeps the cwd off sys.path, so a stray json.py there can't shadow
the stdlib. It reads the hook's stdin JSON, updates the state file and exits.
Only hook_event_name, session_id, agent_id and agent_type are used; the rest,
such as SubagentStop's last_assistant_message, is ignored. It never writes to
stdout (Claude Code would parse that as hook output) and always exits 0, so it
can't block or change a subagent; failures go to .state/errors.log.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from usage.agents import record_subagent_event
from usage.error_log import log_error
from usage.paths import ERROR_LOG, STATE_FILE
from usage.store import HOOK_LOCK_WAIT_S, update_state
from usage.times import local_now


def record_hook_event(raw_input: bytes, state_file: Path, now: datetime) -> None:
    """Add or remove the event's subagent in the state file.

    Raises:
        ValueError: The input isn't JSON, or isn't a JSON object.
        StateLockTimeoutError: Another writer held the lock too long.
        OSError: The state file couldn't be read or written.
    """
    # Lenient decode: a bad byte in a part that isn't used (the last assistant
    # message) mustn't lose the event.
    event = json.loads(raw_input.decode("utf-8", errors="replace"))
    if not isinstance(event, dict):
        raise ValueError(f"hook input isn't a JSON object: {type(event).__name__}")

    def change(state: dict[str, Any], at: datetime) -> dict[str, Any]:
        return record_subagent_event(state, event, at)

    update_state(state_file, change, now, HOOK_LOCK_WAIT_S)


def main() -> int:
    """Hook entry point. Always returns 0."""
    try:
        # No size cap: SubagentStop's last_assistant_message can be large, and a
        # cut-off input wouldn't parse, which would lose the stop.
        record_hook_event(sys.stdin.buffer.read(), STATE_FILE, local_now())
    except Exception as error:  # noqa: BLE001 - a hook must never fail the session's turn
        log_error(ERROR_LOG, "hook", error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
