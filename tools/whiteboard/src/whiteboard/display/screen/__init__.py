"""Public API of whiteboard.display.screen: find the projector and open the board kiosk on it."""

from whiteboard.display.screen.kiosk import (
    EdgeNotFoundError,
    KioskWindow,
    find_edge,
    kiosk_command,
    launch_kiosk,
)
from whiteboard.display.screen.kiosk_processes import close_kiosk, find_kiosk_browser_pids
from whiteboard.display.screen.monitors import (
    Monitor,
    ProjectorNotFoundError,
    find_projector,
    list_monitors,
    pick_projector,
)

__all__ = [
    "EdgeNotFoundError",
    "KioskWindow",
    "Monitor",
    "ProjectorNotFoundError",
    "close_kiosk",
    "find_edge",
    "find_kiosk_browser_pids",
    "find_projector",
    "kiosk_command",
    "launch_kiosk",
    "list_monitors",
    "pick_projector",
]
