"""Decide when to tell an agent its context usage, and what to say.

Quiet below 40%. From there it speaks once per new 10% band, and once more on
crossing the handoff threshold, where the line becomes a firm instruction.
"""

QUIET_BELOW_PCT = 40
BAND_PCT = 10


def usage_level(used_pct: float, threshold_pct: int) -> int:
    """Return the highest announce mark at or below `used_pct`, or 0 if none.

    Marks are 40, 50, ... 100 plus the threshold itself, so crossing 75% speaks
    even though 75 is inside the 70% band.
    """
    marks = [*range(QUIET_BELOW_PCT, 101, BAND_PCT), threshold_pct]
    reached = [mark for mark in marks if mark <= used_pct]
    return max(reached, default=0)


def announcement(used_pct: float, threshold_pct: int) -> str:
    """Return the line to inject for `used_pct` of the context window."""
    shown = int(used_pct)
    if used_pct < threshold_pct:
        return f"Context: {shown}% used (handoff at {threshold_pct}%)."
    return (
        f"Context: {shown}% used, past the {threshold_pct}% handoff line. "
        "Stop starting new work and hand off now, per AGENTS.md section 4."
    )


def decide(used_pct: float, threshold_pct: int, last_level: int) -> tuple[int, str | None]:
    """Return (level to remember, line to inject or None).

    Speaks only when the level rose past `last_level`. The new level is always
    remembered, so after a compaction drops usage, climbing again re-announces.
    """
    level = usage_level(used_pct, threshold_pct)
    if level > last_level:
        return level, announcement(used_pct, threshold_pct)
    return level, None
