"""darken_projector: sleep's projector step, the night view or a black window over it.

Part of SleepMode.sleep (control.machine). When the whiteboard can't show the night
view, the projector gets a black window and the whiteboard daemon is started if it's
down. The daemon resumes the night view by itself once up, and the keeper's night guard
uncovers the projector once it shows.
"""

import logging
from datetime import datetime

from signal_displays import Monitor

from sleepmode.control.deps import SleepDeps
from sleepmode.screens import BLACK_PAGE, BLACK_WINDOW, NIGHT_SKY, MonitorResult
from sleepmode.whiteboard_link import WhiteboardUnavailableError, night_seed

log = logging.getLogger(__name__)

# Short: it's read out by voice. The keeper retries the night view (night_guard).
NO_NIGHT_VIEW_YET = "whiteboard not up; the night view shows once it is"


def darken_projector(
    deps: SleepDeps, projector: Monitor, night_sky: bool, now: datetime
) -> tuple[MonitorResult, str | None]:
    """Ask the whiteboard for the night view; fall back to a black window.

    Args:
        deps: Sleep's collaborators (whiteboard and start_whiteboard are used).
        projector: The projector's display.
        night_sky: The sky, or a black page.
        now: The current time (picks tonight's seed).

    Returns:
        The projector's result, and a note if the whiteboard daemon couldn't be started.
        Never raises: a failed start is only that note.
    """
    rect = (projector.x, projector.y, projector.width, projector.height)
    try:
        deps.whiteboard.show(night_seed(now), night_sky)
    except WhiteboardUnavailableError as error:
        log.warning("%s; covering the projector with a black window", error)
        result = MonitorResult(
            projector.device_name,
            projector.friendly_name,
            BLACK_WINDOW,
            NO_NIGHT_VIEW_YET,
            rect,
            is_projector=True,
        )
        return result, _start_whiteboard(deps)
    method = NIGHT_SKY if night_sky else BLACK_PAGE
    result = MonitorResult(
        projector.device_name, projector.friendly_name, method, "", rect, is_projector=True
    )
    return result, None


def _start_whiteboard(deps: SleepDeps) -> str | None:
    """Start the whiteboard daemon if it's down; return a note if that failed."""
    try:
        deps.start_whiteboard()
    except OSError as error:
        log.warning("couldn't start the whiteboard daemon: %s", error)
        return f"Couldn't start the whiteboard: {error}"
    return None
