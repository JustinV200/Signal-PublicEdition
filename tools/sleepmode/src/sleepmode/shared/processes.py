"""Processes by pid: whether one is still running, and when it started.

Shared by sleepmode.keeper (its own pid in the state file) and sleepmode.whiteboard_link
(the whiteboard daemon's pid in its discovery file). A pid plus its creation time names
one process, since a reused pid comes with a new creation time.
"""

import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger(__name__)

PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
_FILETIME_HIGH_SHIFT = 32


def is_process_alive(pid: int, created: int | None = None) -> bool:
    """True if a process with this id is running.

    Args:
        pid: The process id.
        created: Its recorded creation time (process_creation_time). If given, a process
            that started at another time (a reused pid) doesn't count; if None, any
            process with this id does (best-effort: ids can be reused).
    """
    kernel32 = open_kernel32()
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        if code.value != STILL_ACTIVE:
            return False
        return created is None or is_same_process(kernel32, handle, created)
    finally:
        kernel32.CloseHandle(handle)


def process_creation_time(pid: int) -> int:
    """When the process started, as a FILETIME count (100 ns ticks since 1601).

    Raises:
        OSError: The process can't be opened (it's gone, or access is denied).
    """
    kernel32 = open_kernel32()
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _creation_time(kernel32, handle)
    finally:
        kernel32.CloseHandle(handle)


def is_same_process(kernel32: ctypes.WinDLL, handle: int, created: int) -> bool:
    """True if the process behind handle started at `created`; False if it can't be told."""
    try:
        return _creation_time(kernel32, handle) == created
    except OSError as error:
        log.warning("can't read the process's start time: %s", error)
        return False


def _creation_time(kernel32: ctypes.WinDLL, handle: int) -> int:
    """GetProcessTimes' creation time as one integer; raises OSError if Windows won't say."""
    creation, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    times = (ctypes.byref(creation), ctypes.byref(exited), ctypes.byref(kernel))
    if not kernel32.GetProcessTimes(handle, *times, ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    return (creation.dwHighDateTime << _FILETIME_HIGH_SHIFT) | creation.dwLowDateTime


def open_kernel32() -> ctypes.WinDLL:
    """kernel32 with the signatures sleepmode calls (64-bit handles need explicit types)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32
