"""Claude Code status line command: record the session's usage, print a short usage line.

Run as `<tools/usage venv>/Scripts/python.exe -I -m usage.statusline`. It runs
in every repo's sessions, so -I keeps the cwd off sys.path: a stray json.py
there would otherwise shadow the stdlib, crashing the line and running that
file. Claude Code pipes the session's JSON to stdin and shows stdout as the
status line, e.g. `5h 42% · wk 18% · 2 agents (5 all)`: this session's
subagents, then the total across sessions when it differs. It runs at session start,
after each assistant message and on refreshInterval, so it also keeps the
state file's subagent count pruned.

It must never fail or hang: any error still prints MINIMAL_LINE and exits 0
(the error goes to .state/errors.log), and the lock wait is bounded. A failed
write (lock timeout, or a reader holding the file on Windows) still prints the
known numbers, merged in memory.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from usage.agents import prune_subagents
from usage.error_log import log_error
from usage.paths import ERROR_LOG, STATE_FILE
from usage.rate_limits import merge_rate_limits
from usage.store import StateLockTimeoutError, read_state, update_state
from usage.times import local_now

# The status JSON is a few KiB; this only bounds a runaway input.
MAX_STDIN_BYTES = 1024 * 1024
MINIMAL_LINE = "usage --"
SEPARATOR = " · "
UNKNOWN_PCT = "--"


def render_status_line(raw_input: bytes, state_file: Path, now: datetime) -> str:
    """Merge the input's rate_limits into the state file and return the status line.

    If the write fails for a busy lock or file, it's logged and the line is
    built from a read-only merge instead.

    Args:
        raw_input: The status line's stdin JSON.
        state_file: The shared state file.
        now: The current time (aware).

    Raises:
        ValueError: The input isn't JSON.
        OSError: The state file couldn't be read.
    """
    payload = json.loads(raw_input)
    is_object = isinstance(payload, dict)
    rate_limits = payload.get("rate_limits") if is_object else None
    session_id = payload.get("session_id") if is_object else None

    def change(state: dict[str, Any], at: datetime) -> dict[str, Any]:
        return prune_subagents(merge_rate_limits(state, rate_limits, at), at)

    try:
        state = update_state(state_file, change, now)
    except (StateLockTimeoutError, PermissionError) as error:
        log_error(ERROR_LOG, "statusline", error)
        state = change(read_state(state_file), now)
    return format_line(state, session_id)


def format_line(state: dict[str, Any], session_id: object = None) -> str:
    """`5h 42% · wk 18% · 2 agents (5 all)` from a merged, pruned state.

    `--` marks an unknown window. The agent count is `session_id`'s, with the
    total across sessions added when it differs.
    """
    total = state["active_subagents"]
    session = state["sessions"].get(session_id) if isinstance(session_id, str) else None
    own = len(session["agents"]) if session else 0
    agents = f"{own} agent" if own == 1 else f"{own} agents"
    parts = [
        f"5h {_percent_text(state['five_hour'])}",
        f"wk {_percent_text(state['seven_day'])}",
        agents if own == total else f"{agents} ({total} all)",
    ]
    return SEPARATOR.join(parts)


def _percent_text(window: dict[str, Any] | None) -> str:
    return f"{round(window['used_pct'])}%" if window else UNKNOWN_PCT


def _read_piped_stdin() -> bytes:
    # A terminal run has no piped input; reading would wait forever.
    if sys.stdin is None or sys.stdin.isatty():
        return b""
    return sys.stdin.buffer.read(MAX_STDIN_BYTES)


def main() -> int:
    """Status line entry point. Always prints a line and returns 0."""
    try:
        line = render_status_line(_read_piped_stdin(), STATE_FILE, local_now())
    except Exception as error:  # noqa: BLE001 - the status line must always print
        log_error(ERROR_LOG, "statusline", error)
        line = MINIMAL_LINE
    try:
        # UTF-8 explicitly: a piped stdout on Windows defaults to cp1252, which mangles "·".
        sys.stdout.buffer.write(f"{line}\n".encode())
        sys.stdout.flush()
    except OSError as error:  # Claude Code cancelled this run and closed the pipe.
        log_error(ERROR_LOG, "statusline", error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
