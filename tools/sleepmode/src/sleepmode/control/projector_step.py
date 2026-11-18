"""darken_projector: sleep's projector step, the night view or a black window over it.

Part of SleepMode.sleep (control.machine). The projector counts as showing the night
sky only once a board page really shows it (is_showing); until then it's a black
window, waiting for the whiteboard. A daemon that's down is started here. The keeper's
night guard keeps repairing it (starting the daemon, or asking it to reopen its kiosk)
and uncovers the projector once the sky shows.
"""

import logging
from datetime import datetime

from signal_displays import Monitor

from sleepmode.control.deps import SleepDeps
from sleepmode.screens import BLACK_WINDOW, NIGHT_SKY, MonitorResult
from sleepmode.whiteboard_link import WhiteboardUnavailableError, night_seed

log = logging.getLogger(__name__)

# Short: it's read out by voice. The keeper retries the night view (night_guard).
WAITING_FOR_WHITEBOARD = "waiting for the whiteboard; the night sky shows once it's up"


def darken_projector(
    deps: SleepDeps, projector: Monitor, now: datetime
) -> tuple[MonitorResult, str | None]:
    """Ask the whiteboard for the night view; until a page shows it, a black window.

    Args:
        deps: Sleep's collaborators (whiteboard and start_whiteboard are used).
        projector: The projector's display.
        now: The current time (picks tonight's seed).

    Returns:
        The projector's result: NIGHT_SKY only if a page shows the night view now,
        else BLACK_WINDOW waiting for the whiteboard. Then a note if the whiteboard
        daemon couldn't be started. Never raises: a failed start is only that note.
    """
    note = None
    try:
        deps.whiteboard.show(night_seed(now))
        is_showing = deps.whiteboard.is_showing()
    except WhiteboardUnavailableError as error:
        log.warning("%s; covering the projector with a black window", error)
        is_showing, note = False, _start_whiteboard(deps)
    method, detail = (NIGHT_SKY, "") if is_showing else (BLACK_WINDOW, WAITING_FOR_WHITEBOARD)
    rect = (projector.x, projector.y, projector.width, projector.height)
    result = MonitorResult(
        projector.device_name, projector.friendly_name, method, detail, rect, is_projector=True
    )
    return result, note


def _start_whiteboard(deps: SleepDeps) -> str | None:
    """Start the whiteboard daemon if it's down; return a note if that failed."""
    try:
        deps.start_whiteboard()
    except OSError as error:
        log.warning("couldn't start the whiteboard daemon: %s", error)
        return f"Couldn't start the whiteboard: {error}"
    return None
