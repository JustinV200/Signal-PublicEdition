"""Finds the projector and builds the board page kiosk on it, for the daemon.

A missing projector or Edge isn't fatal: the daemon keeps serving the API and
the board page, logs how to open the page by hand, and uses a 1280x720 stage.
The kiosk's watchdog (watchdog.py) opens it, and opens it again whenever it's gone.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from whiteboard.config import DisplaySettings
from whiteboard.display.screen import (
    Monitor,
    ProjectorNotFoundError,
    close_kiosk,
    find_projector,
    launch_kiosk,
)

logger = logging.getLogger(__name__)

# The stage size used when no projector is connected (the brief's projector).
DEFAULT_PROJECTOR_SIZE = (1280, 720)
EDGE_PROFILE_DIR = "edge-profile"
BOARD_PATH = "/board"


def find_projector_monitor(display: DisplaySettings) -> Monitor | None:
    """Find the projector by [display] name_match, or None (logged) if there isn't one."""
    try:
        monitor = find_projector(display.name_match)
    except (ProjectorNotFoundError, OSError) as error:
        logger.error("no projector found, so the kiosk won't open: %s", error)
        return None
    logger.info(
        "projector: %s (%s) %dx%d at (%d,%d)",
        monitor.friendly_name or "?",
        monitor.device_name,
        monitor.width,
        monitor.height,
        monitor.x,
        monitor.y,
    )
    return monitor


def projector_size(monitor: Monitor | None) -> tuple[int, int]:
    """The stage size: the projector's logical (CSS) pixels, or the default without one.

    Logical, not physical: the S2-TEK reports 1920x1080 at 150% scale, and the
    kiosk page is 1280x720 CSS pixels, so a 1280x720 stage maps 1:1 onto it.
    """
    return monitor.logical_size if monitor is not None else DEFAULT_PROJECTOR_SIZE


@dataclass(frozen=True)
class Kiosk:
    """The board page's Edge kiosk on the projector, found again by its profile folder."""

    url: str
    monitor: Monitor
    profile_dir: Path
    edge_path: str

    def open(self) -> None:
        """Open the kiosk, closing one already using this profile first.

        Raises:
            EdgeNotFoundError: msedge.exe can't be found.
            OSError: Edge can't be started, or a stale kiosk can't be queried.
        """
        launch_kiosk(self.url, self.monitor, self.profile_dir, self.edge_path)

    def close(self) -> None:
        """Close the kiosk (gracefully, then forcibly); no error if it's gone.

        Raises:
            OSError: Its processes can't be queried.
        """
        close_kiosk(self.profile_dir)


def build_kiosk(
    display: DisplaySettings, monitor: Monitor | None, state_dir: Path, token: str
) -> Kiosk | None:
    """The kiosk to keep on the projector, or None (logged) when it's off.

    Args:
        display: [display] settings (port, launch_kiosk, edge_path).
        monitor: The projector, or None (no projector: no kiosk).
        state_dir: Holds the kiosk's own Edge profile.
        token: The daemon token. The kiosk URL carries it once, to get the page cookie.
    """
    if not display.launch_kiosk or monitor is None:
        # The token is a secret, so the log shows where to find it, not the token itself.
        by_hand = f"http://127.0.0.1:{display.port}{BOARD_PATH}?token=<contents of .state/token>"
        logger.info("kiosk not launched; open %s on the projector by hand", by_hand)
        return None
    url = f"http://127.0.0.1:{display.port}{BOARD_PATH}?token={token}"
    return Kiosk(url, monitor, state_dir / EDGE_PROFILE_DIR, display.edge_path)
