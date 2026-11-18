"""repair_night_view: get the whiteboard back to showing the night view on the projector.

The keeper's night guard calls this while the projector is covered and the night
view isn't on a page: the daemon may be down (crashed, never started), or up with
no page because its Edge kiosk closed (an update, a crash). A daemon that's down is
started (it opens on the night view by itself); one that's up is asked to reopen
its kiosk (POST /api/kiosk/open, which the daemon's own watchdog backs off).
"""

import logging
from collections.abc import Callable

from sleepmode.whiteboard_link.night_view import NightViewClient

log = logging.getLogger(__name__)


def repair_night_view(client: NightViewClient, start_daemon: Callable[[], bool]) -> None:
    """Start the whiteboard daemon if it's down, else ask it to reopen its kiosk.

    Args:
        client: The night view client (finds the daemon through its discovery files).
        start_daemon: Starts the daemon unless it's running (start_whiteboard_if_down).

    Raises:
        OSError: The daemon couldn't be started.
        WhiteboardUnavailableError: The daemon is up but couldn't reopen its kiosk.
    """
    if not client.is_daemon_running():
        start_daemon()
        return
    if client.open_kiosk():
        log.info("the whiteboard had no page on the projector; it tried to reopen its kiosk")
