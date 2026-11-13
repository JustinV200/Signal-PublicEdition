"""format_local_time: epoch timestamps as short local date-times for listings and status.

Shared by the daemon's status views, the transcript listings and the CLI, so
every time the tool shows reads the same way.
"""

from datetime import datetime

MS_PER_SECOND = 1000
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_local_time(epoch_seconds: float) -> str:
    """Format seconds since the epoch in this PC's local time zone.

    Args:
        epoch_seconds: A Unix timestamp in seconds.

    Returns:
        E.g. "2026-10-19 15:42:07".
    """
    return datetime.fromtimestamp(epoch_seconds).strftime(TIME_FORMAT)


def format_local_time_ms(epoch_ms: int) -> str:
    """Like format_local_time, for a timestamp in milliseconds (the SDK's transcript times)."""
    return format_local_time(epoch_ms / MS_PER_SECOND)
