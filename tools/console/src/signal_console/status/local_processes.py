"""Is the desktop browser or Docker Desktop running? One read-only scan of the process table.

The desktop browser is tools/browser's dedicated Edge profile: an msedge.exe
whose command line names that profile folder. Docker Desktop (which the
docker browser's containers need) is its backend process. Listing every
process costs tens of milliseconds, so callers run this in a thread and cache it.
"""

from dataclasses import dataclass
from pathlib import Path

import psutil

EDGE_EXE = "msedge.exe"
# Docker Desktop's engine-side process names on Windows (the UI alone isn't enough).
DOCKER_EXES = frozenset({"com.docker.backend.exe", "com.docker.build.exe", "dockerd.exe"})


@dataclass(frozen=True)
class LocalProcesses:
    """What the scan found."""

    is_desktop_browser_running: bool
    is_docker_running: bool


def scan_processes(browser_profile: Path) -> LocalProcesses:
    """Scan the process table once.

    Args:
        browser_profile: tools/browser's Edge profile folder.
    """
    profile = str(browser_profile).lower()
    is_browser = is_docker = False
    for process in psutil.process_iter(["name"]):
        name = (process.info.get("name") or "").lower()
        if name in DOCKER_EXES:
            is_docker = True
        elif name == EDGE_EXE and not is_browser:
            is_browser = _names_profile(process, profile)
    return LocalProcesses(is_browser, is_docker)


def _names_profile(process: psutil.Process, profile: str) -> bool:
    # Only Edge processes get their command line read: that's the slow part of a scan.
    try:
        return any(profile in part.lower() for part in process.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
