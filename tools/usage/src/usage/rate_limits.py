"""Merge the status line's rate_limits into the state's five_hour and seven_day windows.

Usage is account-wide, but each session only knows the values from its own
last API response, and an idle session re-sends those stale values on every
refresh. Usage only grows within a window, so the newest data is:
- for the same window (reset times within SAME_WINDOW_TOLERANCE), the higher
  percentage;
- otherwise the later reset time, which is a newer window.
A window this session doesn't send keeps the known value until its reset time
passes, and then it's dropped.

Stored form of a window: {"used_pct": 42.0, "resets_at": "<ISO local>",
"changed_at": "<ISO local>"}, or None. changed_at is when used_pct or
resets_at last changed; a re-sent value keeps it, so a display can show how
old the numbers really are.
"""

import math
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from usage.times import from_epoch, parse_iso, to_iso

WINDOW_NAMES = ("five_hour", "seven_day")
# Reset times of one window could differ by rounding between responses; a new
# window resets hours (5 h) or days (7 d) later, far beyond this.
SAME_WINDOW_TOLERANCE = timedelta(minutes=5)


class Window(NamedTuple):
    """One usage window: percent used (0-100) and when it resets (aware)."""

    used_pct: float
    resets_at: datetime
    # When this value was first seen; None for a stored window from before changed_at existed.
    changed_at: datetime | None = None


def merge_rate_limits(state: dict[str, Any], rate_limits: object, now: datetime) -> dict[str, Any]:
    """The state with each window updated from a status line's `rate_limits` object.

    Args:
        state: The current state; its windows may be missing or malformed.
        rate_limits: The input's `rate_limits` value, which may be absent (None) or malformed.
        now: The current time (aware); windows that reset at or before it are dropped.

    Returns:
        A new state dict; `state` isn't changed.
    """
    sent = rate_limits if isinstance(rate_limits, dict) else {}
    merged = dict(state)
    for name in WINDOW_NAMES:
        known = _live(_read_stored(state.get(name)), now)
        incoming = _live(_read_sent(sent.get(name), now), now)
        merged[name] = _to_stored(_newest(known, incoming), now)
    return merged


def _to_stored(window: Window | None, now: datetime) -> dict[str, Any] | None:
    if window is None:
        return None
    return {
        "used_pct": window.used_pct,
        "resets_at": to_iso(window.resets_at),
        "changed_at": to_iso(window.changed_at or now),
    }


def _newest(known: Window | None, incoming: Window | None) -> Window | None:
    if incoming is None:
        return known
    if known is None:
        return incoming
    if abs(incoming.resets_at - known.resets_at) <= SAME_WINDOW_TOLERANCE:
        # A tie keeps the known window, and with it its changed_at.
        return incoming if incoming.used_pct > known.used_pct else known
    return incoming if incoming.resets_at > known.resets_at else known


def _live(window: Window | None, now: datetime) -> Window | None:
    return window if window is not None and window.resets_at > now else None


def _read_sent(value: object, now: datetime) -> Window | None:
    """A window from the status line's {"used_percentage", "resets_at": epoch s}, seen `now`."""
    if not isinstance(value, dict):
        return None
    used_pct = _percent(value.get("used_percentage"))
    resets_at = from_epoch(value.get("resets_at"))
    return Window(used_pct, resets_at, now) if used_pct is not None and resets_at else None


def _read_stored(value: object) -> Window | None:
    """A window from the state file's {"used_pct", "resets_at": ISO}."""
    if not isinstance(value, dict):
        return None
    used_pct = _percent(value.get("used_pct"))
    resets_at = parse_iso(value.get("resets_at"))
    if used_pct is None or not resets_at:
        return None
    return Window(used_pct, resets_at, parse_iso(value.get("changed_at")))


def _percent(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)
