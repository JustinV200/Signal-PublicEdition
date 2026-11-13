"""The usage line shown beside the tasks: 5-hour and weekly windows, running agents, and its age.

Read from tools/usage's usage.json (format in its README). Its reader rules
apply: read the file whole and quickly, and treat a PermissionError (a writer
mid-replace) or bad JSON as "keep your last copy", which is why read_usage
returns None then. The checks the README leaves to the display are done here:
a window whose resets_at has passed is unknown, and an agent not seen for
2 hours is not counted.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Matches tools/usage's STALE_AGENT_HOURS.
AGENT_FRESH = timedelta(hours=2)


@dataclass(frozen=True)
class UsageWindow:
    """One rate-limit window: percent used and when it resets."""

    used_pct: float
    resets_at: datetime


@dataclass(frozen=True)
class UsageSummary:
    """What the display needs from usage.json.

    Attributes:
        five_hour: The 5-hour window, or None when unknown or already reset.
        seven_day: The weekly window, the same way.
        agents: Subagents seen in the last AGENT_FRESH, over every session.
        updated_at: The file's last write, or None if it has none.
    """

    five_hour: UsageWindow | None
    seven_day: UsageWindow | None
    agents: int
    updated_at: datetime | None


NO_USAGE = UsageSummary(None, None, 0, None)


def read_usage(path: Path, now: datetime) -> UsageSummary | None:
    """Summarise usage.json; NO_USAGE if it doesn't exist, None if it can't be read right now.

    Args:
        path: tools/usage/.state/usage.json.
        now: The current time (aware), for the reset and freshness checks.
    """
    try:
        payload = json.loads(path.read_bytes())
    except FileNotFoundError:
        return NO_USAGE
    except (OSError, ValueError):
        return None  # retried on the caller's next tick
    if not isinstance(payload, dict):
        return None
    sessions = payload.get("sessions")
    return UsageSummary(
        _window(payload.get("five_hour"), now),
        _window(payload.get("seven_day"), now),
        _fresh_agents(sessions if isinstance(sessions, dict) else {}, now),
        _time(payload.get("updated_at")),
    )


def _window(raw: Any, now: datetime) -> UsageWindow | None:
    if not isinstance(raw, dict):
        return None
    used, resets_at = raw.get("used_pct"), _time(raw.get("resets_at"))
    if isinstance(used, bool) or not isinstance(used, int | float) or resets_at is None:
        return None
    return UsageWindow(float(used), resets_at) if resets_at > now else None


def _fresh_agents(sessions: dict[str, Any], now: datetime) -> int:
    count = 0
    for session in sessions.values():
        agents = session.get("agents") if isinstance(session, dict) else None
        for agent in agents if isinstance(agents, list) else []:
            seen = _time(agent.get("seen_at")) if isinstance(agent, dict) else None
            count += seen is not None and now - seen < AGENT_FRESH
    return count


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    return at if at.tzinfo else at.astimezone()
