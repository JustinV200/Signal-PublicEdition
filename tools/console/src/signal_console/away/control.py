"""Away mode for the System page: read it, and turn it on or off when the owner clicks.

Away mode is the brief's (packages/brief): while it's on, sessions hold their
news for the owner. This is the one console control that acts directly instead of
asking the orchestrator: it's the owner's own toggle, the same as typing
`brief away on|off`. It runs only from the page's POST /api/away, behind the
console's login and origin checks, never on a message or agent request.
"""

from datetime import datetime
from typing import Any

from signal_brief import AwayStatus, BriefPaths, away_off, away_on, away_status, parse_until

MAX_UNTIL_CHARS = 40


def away_payload(paths: BriefPaths, now: datetime) -> dict[str, Any]:
    """The page's away block: `{state: here|away|asleep, endsAt, note}`.

    Raises:
        BriefLogError: The away state couldn't be read.
    """
    return _payload(away_status(paths, now))


def set_away(paths: BriefPaths, now: datetime, is_on: bool, until: str = "") -> dict[str, Any]:
    """Turn away mode on (until `until`, else the brief's 3-day default) or off.

    Args:
        paths: The brief's state files.
        now: The current time (aware).
        is_on: True for away, False for "I'm back".
        until: What the owner typed: "", a weekday, "tomorrow", an ISO date or date-time.

    Returns:
        The away block after the change.

    Raises:
        ValueError: `until` is too long, unreadable or already past.
        BriefLogError: The state couldn't be locked or written.
    """
    if len(until) > MAX_UNTIL_CHARS:
        raise ValueError(f"the end time is longer than {MAX_UNTIL_CHARS} characters")
    if is_on:
        return _payload(away_on(paths, now, parse_until(until, now)))
    away_off(paths, now)
    return away_payload(paths, now)


def _payload(status: AwayStatus) -> dict[str, Any]:
    return {
        "state": status.state,
        # Only an end the owner gave: the 3-day default would read as "away until <now>".
        "endsAt": status.ends_at.isoformat() if status.ends_at and status.end_given else None,
        "note": status.note,
    }
