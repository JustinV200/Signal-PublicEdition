"""How a claim reads to the owner: its default label and how long ago it was made.

A claim made without `--label` (and every auto-claim from `console tasks set`)
is labelled with the local time it was made, so sessions can be told apart in
the feed and the status line's tooltip. The feed's claim note says "linked 26
days ago" rather than the claim file's raw UTC stamp.
"""

from datetime import datetime, timedelta

# e.g. "Tue 17 Nov 10:25": short, local, and different for every session.
LABEL_TIME_FORMAT = "%a %d %b %H:%M"
# Largest unit first: an age reads in the biggest whole unit it has.
AGE_UNITS = (
    ("day", timedelta(days=1)),
    ("hour", timedelta(hours=1)),
    ("minute", timedelta(minutes=1)),
)


def default_label(now: datetime) -> str:
    """The label for a claim made at `now` with none given: its local time, `Tue 17 Nov 10:25`."""
    return now.astimezone().strftime(LABEL_TIME_FORMAT)


def claimed_ago(claimed_at: str, now: datetime) -> str | None:
    """`linked just now`, `linked 5 minutes ago`, `linked 26 days ago`: the page says "linked".

    Args:
        claimed_at: The claim's ISO time with its offset (the claim file's `claimedAt`).
        now: The current time, timezone-aware.

    Returns:
        The words, or None when `claimed_at` isn't an ISO time with an offset
        (an old or hand-edited file), so the caller leaves the age out.
    """
    try:
        made = datetime.fromisoformat(claimed_at)
    except ValueError:
        return None
    if made.tzinfo is None:
        return None
    age = now - made
    for unit, size in AGE_UNITS:
        count = age // size
        if count >= 1:
            return f"linked {count} {unit}{'' if count == 1 else 's'} ago"
    # Under a minute, or a clock that ran backwards.
    return "linked just now"
