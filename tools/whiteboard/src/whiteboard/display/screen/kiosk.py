"""Open the board page in a fullscreen Edge kiosk window on the projector.

Edge runs with its own `--user-data-dir` (in .state/edge-profile), so it's a separate
browser instance from the owner's everyday Edge and never touches their profile.
That profile path is also how the kiosk is found again to close it (kiosk_processes.py).
`--window-position` takes logical (DIP) desktop coordinates, i.e. physical pixels
divided by the display scale. That's how the window opens on the projector before
kiosk mode makes it fullscreen there.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from whiteboard.display.screen.kiosk_processes import close_kiosk
from whiteboard.display.screen.monitors import Monitor

log = logging.getLogger(__name__)

# Where the Edge installer puts msedge.exe, per machine or per user.
_EDGE_INSTALL_DIRS = ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")
_EDGE_RELATIVE_PATH = Path("Microsoft") / "Edge" / "Application" / "msedge.exe"


class EdgeNotFoundError(FileNotFoundError):
    """Raised when msedge.exe can't be found."""


def find_edge(configured_path: str = "") -> Path:
    """Locate msedge.exe: the configured path, else the standard install folders, else PATH.

    Raises:
        EdgeNotFoundError: If none of those has msedge.exe.
    """
    if configured_path:
        path = Path(configured_path)
        if not path.is_file():
            raise EdgeNotFoundError(f"display.edge_path does not exist: {path}")
        return path
    for variable in _EDGE_INSTALL_DIRS:
        base = os.environ.get(variable)
        if base and (Path(base) / _EDGE_RELATIVE_PATH).is_file():
            return Path(base) / _EDGE_RELATIVE_PATH
    on_path = shutil.which("msedge")
    if on_path:
        return Path(on_path)
    raise EdgeNotFoundError("Microsoft Edge (msedge.exe) not found; set display.edge_path")


def kiosk_command(edge: Path, url: str, monitor: Monitor, profile_dir: Path) -> list[str]:
    """Build the Edge command line for a fullscreen kiosk window on `monitor`.

    Args:
        edge: Path to msedge.exe.
        url: The board page URL.
        monitor: The projector, from find_projector.
        profile_dir: Edge's --user-data-dir for this kiosk.

    Returns:
        The argv list for subprocess.
    """
    width, height = monitor.logical_size
    left, top = round(monitor.x / monitor.scale), round(monitor.y / monitor.scale)
    return [
        str(edge),
        "--kiosk",
        url,
        "--edge-kiosk-type=fullscreen",
        f"--window-position={left},{top}",
        f"--window-size={width},{height}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        # A forced kill otherwise brings up "restore pages?" on the projector next time.
        "--hide-crash-restore-bubble",
        "--disable-features=Translate",
    ]


@dataclass(frozen=True)
class KioskWindow:
    """A running kiosk, identified by its Edge profile folder."""

    profile_dir: Path

    def close(self) -> None:
        """Close the kiosk Edge instance (gracefully, then forcibly). No error if it's gone.

        Raises:
            OSError: If its processes can't be queried.
        """
        close_kiosk(self.profile_dir)


def launch_kiosk(url: str, monitor: Monitor, profile_dir: Path, edge_path: str = "") -> KioskWindow:
    """Start Edge fullscreen on the projector showing `url`.

    A kiosk already running with this profile (e.g. left by a crashed daemon) is
    closed first; otherwise Edge would hand the URL to it and not apply the flags.

    Args:
        url: The board page URL, e.g. http://127.0.0.1:8770/board.
        monitor: The projector.
        profile_dir: Edge's --user-data-dir (created if missing).
        edge_path: display.edge_path from config; "" auto-detects.

    Returns:
        The running KioskWindow; call close() to shut it.

    Raises:
        EdgeNotFoundError: If msedge.exe can't be found.
        OSError: If Edge can't be started or a stale kiosk can't be queried.
    """
    command = kiosk_command(find_edge(edge_path), url, monitor, profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    close_kiosk(profile_dir)
    # Log without the URL's query string: it may carry the daemon token.
    log.info("starting Edge kiosk for %s on %s", url.split("?", 1)[0], monitor.device_name)
    # Edge relaunches itself and this process exits at once, so the handle isn't kept.
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return KioskWindow(profile_dir)
