"""Process-lifetime guards for the daemon: one daemon per state_dir, and its CLIs die with it.

- `hold_daemon_lock` takes an exclusive msvcrt lock on state_dir/daemon.lock for
  as long as the daemon runs. A second daemon would resume the same runs and put
  two writers on one SDK session id, which forks its transcript (session-resume
  spike). The OS drops the lock if the daemon dies.
- `join_kill_on_close_job` puts the daemon itself in a kill-on-close Windows job
  (gpu's KillOnCloseJob), so every claude.exe it starts dies with it. Otherwise an
  orphan keeps appending to its transcript and the next resume loads its branch.
"""

import ctypes
import logging
import msvcrt
from ctypes import wintypes
from pathlib import Path
from typing import BinaryIO

from analysis_chamber.gpu import KillOnCloseJob

logger = logging.getLogger(__name__)

LOCK_FILE_NAME = "daemon.lock"


class DaemonRunningError(RuntimeError):
    """Another daemon holds state_dir/daemon.lock."""


def hold_daemon_lock(state_dir: Path) -> BinaryIO:
    """Take the daemon lock; keep the returned file open for the daemon's lifetime.

    Returns:
        The open lock file; `release_daemon_lock` frees it.

    Raises:
        DaemonRunningError: Another daemon holds it.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    handle = open(state_dir / LOCK_FILE_NAME, "a+b")  # noqa: SIM115 (held past this call)
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        handle.close()
        raise DaemonRunningError("an analysis-chamber daemon is already running") from error
    return handle


def release_daemon_lock(handle: BinaryIO) -> None:
    """Free the daemon lock taken by hold_daemon_lock."""
    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    handle.close()


def join_kill_on_close_job() -> KillOnCloseJob | None:
    """Put this process in a kill-on-close job for the rest of its life.

    The job handle is never closed (KillOnCloseJob has no finalizer), so dropping
    the result is fine; Windows closes it, killing the job's processes, at exit.

    Returns:
        The job, or None (with a warning) if Windows refused; the daemon still runs.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    try:
        job = KillOnCloseJob()
        job.add(kernel32.GetCurrentProcess())
    except OSError as error:
        logger.warning("no kill-on-close job (%s); a daemon crash may orphan claude.exe", error)
        return None
    logger.info("daemon is in a kill-on-close job; its agent CLIs die with it")
    return job
