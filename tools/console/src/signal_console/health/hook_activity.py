"""The hook activity rows: the last reply the turn hook brought, and recent hook.log errors.

Both are local reads of .state files, so they work with the server down.
The turn hook's Stop report carries Claude's reply, which the server keeps as a
"claude" message in history.jsonl; the newest one is the last report on record.
Replies reach history only while the server runs, and history is capped, so a
reply from before the current claim says nothing about this session's hook.
hook.log holds one `<local ISO time> <error repr>` line per hook failure. Only
lines from the last 24 hours count as a problem; older ones are history. The
rows give counts and times, never the error text (it could name a pipe).
"""

import json
from datetime import datetime
from pathlib import Path

from signal_console.health.inputs import HealthPaths
from signal_console.health.row import ATTENTION, OK, RECENT_WINDOW, HealthRow
from signal_console.open_hint import open_command
from signal_console.orchestrator import read_claim
from signal_console.paths import HISTORY_FILE, HOOK_LOG_FILE

SHOWN_TIME_FORMAT = "%Y-%m-%d %H:%M"


def last_report_row(paths: HealthPaths) -> HealthRow:
    """When Claude's last reply came through the turn hook.

    Attention when no reply ever has, or when the newest one is older than the
    current claim (this session's hook hasn't been seen working). Ok with no claim.
    """
    at = _last_reply_at(paths.state_dir / HISTORY_FILE)
    if at is None:
        words = "No reply from Claude has come through the turn hook yet."
        fix = "Link a Claude Code session to the console, then let Claude finish one turn."
        return HealthRow("hook-report", "Last hook report", ATTENTION, "none yet", words, fix)
    claimed_at = _claimed_at(paths)
    if claimed_at is not None and at < claimed_at:
        words = (
            "No reply has come through the turn hook since this session linked "
            f"(last one: {_shown(at)})."
        )
        fix = "Open the console, then let Claude finish one turn."
        return HealthRow(
            "hook-report",
            "Last hook report",
            ATTENTION,
            "none since link",
            words,
            fix,
            open_command(paths.tool_root),
        )
    words = f"Claude's last reply came through the turn hook at {_shown(at)}."
    return HealthRow("hook-report", "Last hook report", OK, "received", words)


def hook_errors_row(paths: HealthPaths, now: datetime) -> HealthRow:
    """Attention when a hook logged a failure in the last 24 hours; older lines are history.

    Args:
        paths: Where hook.log is (state_dir).
        now: The current time, timezone-aware.
    """
    log_path = paths.state_dir / HOOK_LOG_FILE
    stamps = _error_stamps(log_path)
    recent = [stamp for stamp in stamps if stamp is not None and now - stamp < RECENT_WINDOW]
    older = len(stamps) - len(recent)
    history = f" ({older} older ones are history)" if older else ""
    if not recent:
        words = f"No hook errors in the last 24 hours{history}."
        return HealthRow("hook-errors", "Hook errors", OK, "none recent", words)
    newest = _shown(max(recent))
    words = f"{len(recent)} hook errors in the last 24 hours, the newest at {newest}{history}."
    fix = f"Read {log_path} for the reason; each line is one failed hook run."
    return HealthRow("hook-errors", "Hook errors", ATTENTION, "recent errors", words, fix)


def _last_reply_at(history: Path) -> datetime | None:
    try:
        lines = history.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue  # A torn last line from a crash; the earlier ones still count.
        data = event.get("data") if isinstance(event, dict) else None
        # data is a dict only when event is one.
        is_reply = isinstance(data, dict) and data.get("role") == "claude"
        if is_reply and event.get("event") == "message":
            return _parse_time(data.get("at"))
    return None


def _claimed_at(paths: HealthPaths) -> datetime | None:
    # Read as claim_check does; a missing, malformed or undated claim counts as none.
    claim = read_claim(paths.state_dir)
    return None if claim is None else _parse_time(claim.claimed_at)


def _error_stamps(log_path: Path) -> list[datetime | None]:
    # One entry per line: its time, or None when the line has no readable one (counted as old).
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [_parse_time(line.split(" ", 1)[0]) for line in lines if line.strip()]


def _parse_time(text: object) -> datetime | None:
    # hook.log writes local time without an offset; astimezone() reads a naive time as local.
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text).astimezone()
    except ValueError:
        return None


def _shown(at: datetime) -> str:
    return at.astimezone().strftime(SHOWN_TIME_FORMAT)
