"""last_minute_boundary_s: when the idle view's clock last changed, on the monotonic clock.

The idle page shows HH:MM and moves its dial's hands on each minute, which the camera
sees but the daemon never sends. BoardController.page_changed_s counts each minute
boundary as a page change while the idle view shows, so the change watcher settles
after the flip and the drift monitor's "page unchanged" rule waits it out too.
"""

from datetime import datetime


def last_minute_boundary_s(monotonic_now: float, wall_now: datetime) -> float:
    """The monotonic time of the most recent wall-clock minute boundary.

    Args:
        monotonic_now: time.monotonic() now.
        wall_now: The local time at that same moment (the page ticks on this clock).

    Returns:
        monotonic_now minus how far into its minute wall_now is.
    """
    return monotonic_now - (wall_now.second + wall_now.microsecond / 1_000_000)
