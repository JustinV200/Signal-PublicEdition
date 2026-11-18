"""Public API of whiteboard.daemon.kiosk: the board page's Edge kiosk on the projector.

find_projector_monitor and projector_size pick the projector and the stage size;
build_kiosk makes the Kiosk; KioskWatchdog opens it and reopens it whenever it's gone;
add_kiosk_routes adds POST /api/kiosk/open.
"""

from whiteboard.daemon.kiosk.routes import add_kiosk_routes
from whiteboard.daemon.kiosk.runner import (
    Kiosk,
    build_kiosk,
    find_projector_monitor,
    projector_size,
)
from whiteboard.daemon.kiosk.watchdog import KioskWatchdog

__all__ = [
    "Kiosk",
    "KioskWatchdog",
    "add_kiosk_routes",
    "build_kiosk",
    "find_projector_monitor",
    "projector_size",
]
