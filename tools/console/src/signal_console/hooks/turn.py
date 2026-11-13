"""Claude Code turn hook: tell the console when the claimed orchestrator's turns start and end.

Run as `<console venv>\\Scripts\\python.exe -m signal_console.hooks.turn`,
registered async for UserPromptSubmit (start), Stop and StopFailure (end) and
Notification with matcher idle_prompt (idle; the server only lets it end a
turn at least a minute old). Stop's report also carries the turn's final
message, which shows in the console, its background task count and its
effort level (for the model strip's "now").

It fires for every session in the repo, so it does nothing unless this
session's CLAUDE_CODE_MESSAGING_SOCKET is the one `console claim` saved. It
never writes to stdout (for UserPromptSubmit that would become context Claude
sees) and always exits 0, even when the console server isn't running. Other
failures go to .state/hook.log.
"""

import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from signal_console.hooks.hook_log import log_hook_failure
from signal_console.hooks.reply import fit_reply
from signal_console.local_api import HOOK_TURN_PATH, ConsoleNotRunningError, post_local
from signal_console.orchestrator import SOCKET_ENV, read_claim
from signal_console.paths import STATE_DIR

POST_TIMEOUT_S = 1.5
MAX_STDIN_BYTES = 4 * 1024 * 1024
EVENT_PHASES = {
    "UserPromptSubmit": "start",
    "Stop": "end",
    "StopFailure": "end",
    "Notification": "idle",
}
IDLE_NOTIFICATION = "idle_prompt"
# Claude Code sets this for hooks; the server checks the value.
EFFORT_ENV = "CLAUDE_EFFORT"

PostLocal = Callable[[Path, str, dict[str, Any], float], dict[str, Any]]


def report_turn(
    raw_input: bytes,
    environ: Mapping[str, str],
    state_dir: Path,
    at: float,
    post: PostLocal = post_local,
) -> bool:
    """Report this hook event to the console if this is the claimed session.

    Args:
        raw_input: The hook's JSON input (hook_event_name, session_id, ...).
        environ: The hook's environment (Claude Code sets the session's inbox socket).
        state_dir: The console's .state folder.
        at: Epoch seconds when the hook process started (async hooks can land out of order).
        post: Posts to the server; tests may pass a fake.

    Returns:
        True if it posted, False if this isn't the claimed session or an event it reports.

    Raises:
        ConsoleNotRunningError: No console server is answering.
        ValueError: The input isn't a JSON object.
        OSError: The POST failed.
    """
    socket = environ.get(SOCKET_ENV)
    claim = read_claim(state_dir) if socket else None
    if claim is None or socket != claim.socket:
        return False
    payload = json.loads(raw_input)
    if not isinstance(payload, dict):
        raise ValueError("the hook input isn't a JSON object")
    event = payload.get("hook_event_name")
    phase = EVENT_PHASES.get(event)
    # The idle_prompt matcher should already keep other notifications away.
    is_other_notification = payload.get("notification_type") != IDLE_NOTIFICATION
    if phase is None or (event == "Notification" and is_other_notification):
        return False
    body: dict[str, Any] = {"phase": phase, "session_id": payload.get("session_id"), "at": at}
    if event == "Stop":
        body |= _stop_fields(payload, body, environ.get(EFFORT_ENV))
    post(state_dir, HOOK_TURN_PATH, body, POST_TIMEOUT_S)
    return True


def _stop_fields(
    payload: dict[str, Any], body: dict[str, Any], env_effort: str | None
) -> dict[str, Any]:
    # Stop's extras: the background task count, the effort level (the input's
    # effort.level, else $CLAUDE_EFFORT), and the final message cut to fit the body.
    tasks = payload.get("background_tasks")
    fields: dict[str, Any] = {"background_tasks": len(tasks)} if isinstance(tasks, list) else {}
    effort = payload.get("effort")
    level = effort.get("level") if isinstance(effort, dict) else None
    level = level if isinstance(level, str) else env_effort
    if level:
        fields["effort"] = level
    text = payload.get("last_assistant_message")
    return fields | {"text": fit_reply(body | fields, text if isinstance(text, str) else "")}


def main() -> int:
    """Hook entry point. Always returns 0 and never prints."""
    at = time.time()  # first, so the stamp is as close to the event as the hook can get
    try:
        report_turn(sys.stdin.buffer.read(MAX_STDIN_BYTES), os.environ, STATE_DIR, at)
    except ConsoleNotRunningError:
        pass  # The console simply isn't open; nothing to report to.
    except Exception as error:  # noqa: BLE001 - a hook must never fail the session's turn
        log_hook_failure(STATE_DIR, error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
