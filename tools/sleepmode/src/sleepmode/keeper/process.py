"""Ending a keeper that hangs on (whether a pid is running lives in sleepmode.shared).

The recorded keeper pid is the venv's python.exe, which on Windows is a small launcher:
it runs the real interpreter as its child and takes the child down with it. So inside
the keeper that pid is the parent process, and ending the pid ends the keeper. The
launcher's creation time is recorded with its pid: together they name that one process,
since a reused pid comes with a new creation time.
"""

import ctypes
import logging
import os
import time

from sleepmode.shared.processes import (
    PROCESS_QUERY_LIMITED_INFORMATION,
    PROCESS_TERMINATE,
    is_process_alive,
    is_same_process,
    open_kernel32,
)

log = logging.getLogger(__name__)

EXIT_POLL_S = 0.25
_ENDED_EXIT_CODE = 1


def stop_keeper(pid: int, created: int | None, wait_s: float) -> None:
    """Give a keeper that was told to exit wait_s seconds, then end it if it's still running.

    Only that pid is touched, and only while its creation time still matches, so a
    reused pid is left alone (even another python from this venv, such as an MCP
    server). The caller and its parent are never touched: the keeper runs wake()
    itself, and its recorded pid is its own launcher. Never raises.

    Args:
        pid: The keeper's recorded pid (SleepState.keeper_pid).
        created: Its recorded creation time (SleepState.keeper_created). None (a state
            file from before it was recorded) means it's never ended, only waited for.
        wait_s: How long it gets to exit by itself.
    """
    if pid in (os.getpid(), os.getppid()):
        return
    deadline = time.monotonic() + wait_s
    # With the creation time, a pid already reused by another process isn't waited on.
    while is_process_alive(pid, created):
        if time.monotonic() >= deadline:
            _end_if_keeper(pid, created)
            return
        time.sleep(EXIT_POLL_S)


def _end_if_keeper(pid: int, created: int | None) -> None:
    """TerminateProcess the pid if it's still the recorded keeper, logging the outcome."""
    if created is None:
        log.warning("keeper %d is still running, but its start time isn't known; leaving it", pid)
        return
    kernel32 = open_kernel32()
    access = PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        error = ctypes.WinError(ctypes.get_last_error())
        log.warning("keeper %d is still running but can't be opened: %s", pid, error)
        return
    try:
        if not is_same_process(kernel32, handle, created):
            log.warning("pid %d is now another process, not the keeper; leaving it", pid)
            return
        if not kernel32.TerminateProcess(handle, _ENDED_EXIT_CODE):
            error = ctypes.WinError(ctypes.get_last_error())
            log.warning("couldn't end keeper %d: %s", pid, error)
            return
        log.warning("keeper %d was still running after the wake; ended it", pid)
    finally:
        kernel32.CloseHandle(handle)
