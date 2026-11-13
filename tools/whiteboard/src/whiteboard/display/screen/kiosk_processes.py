"""Find and close the kiosk's Edge processes, identified by their own --user-data-dir.

The msedge.exe we start relaunches itself and exits at once, so its Popen
handle is useless for closing the kiosk. Instead, the browser process is found
by the profile path in its command line: it's the msedge.exe without a `--type=`
switch, since helper processes all have one. Command lines of other processes
aren't readable from the standard library, so this asks PowerShell's CIM
cmdlets, which ship with every Windows 11.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

# How long a graceful close (WM_CLOSE) gets before a forced kill.
CLOSE_TIMEOUT_S = 5.0
_POLL_S = 0.25
_PROFILE_ENV = "WHITEBOARD_EDGE_PROFILE"
# Reads the profile path from the environment, so no quoting or wildcard escaping is needed.
_FIND_BROWSER_SCRIPT = (
    "$profile = $env:" + _PROFILE_ENV + ".ToLower(); "
    "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
    "Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($profile) "
    "-and -not $_.CommandLine.Contains('--type=') } | "
    "ForEach-Object { $_.ProcessId }"
)


def find_kiosk_browser_pids(profile_dir: Path) -> list[int]:
    """Return the pids of Edge browser processes using this profile (normally zero or one).

    Raises:
        OSError: If PowerShell can't be run or the query fails.
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _FIND_BROWSER_SCRIPT],
        capture_output=True,
        text=True,
        env={**os.environ, _PROFILE_ENV: str(profile_dir.resolve())},
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"finding kiosk Edge processes failed: {result.stderr.strip()}")
    return [int(line) for line in result.stdout.split() if line.isdigit()]


def close_kiosk(profile_dir: Path) -> None:
    """Close every Edge instance using this profile: WM_CLOSE first, then a forced kill.

    Raises:
        OSError: If the processes can't be queried.
    """
    pids = find_kiosk_browser_pids(profile_dir)
    if not pids:
        return
    # WM_CLOSE to the browser process only. With /T, taskkill would try the
    # children first, which refuse to close without /F.
    _taskkill(pids, force=False)
    deadline = time.monotonic() + CLOSE_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(_POLL_S)
        pids = find_kiosk_browser_pids(profile_dir)
        if not pids:
            return
    log.warning("Edge kiosk didn't close in %.0f s; killing it", CLOSE_TIMEOUT_S)
    _taskkill(pids, force=True)


def _taskkill(pids: list[int], *, force: bool) -> None:
    command = ["taskkill"]
    for pid in pids:
        command += ["/PID", str(pid)]
    if force:
        command += ["/T", "/F"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # Usually "process not found" because it exited meanwhile; worth a log line, not a crash.
        log.info(
            "taskkill %s: %s", " ".join(command[1:]), result.stderr.strip() or result.stdout.strip()
        )
