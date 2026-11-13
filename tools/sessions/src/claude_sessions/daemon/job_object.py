"""kill_children_with_daemon: puts the daemon in a Windows job object that dies with it.

Each session runs a claude.exe, which starts its own MCP servers. If the
daemon is killed hard (Task Manager, a crash), nothing would stop them. A job
object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE fixes that: the daemon holds
the only handle, children join the job automatically, and when the daemon's
process ends Windows closes the handle and kills every process in the job.
Nested jobs (Windows 8+) let this work even when the daemon was started
inside another job.
"""

import ctypes
import logging
import os
from ctypes import wintypes

logger = logging.getLogger(__name__)

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _BasicLimitInformation(ctypes.Structure):
    """JOBOBJECT_BASIC_LIMIT_INFORMATION (winnt.h)."""

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    """IO_COUNTERS (winnt.h)."""

    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION (winnt.h)."""

    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def kill_children_with_daemon() -> bool:
    """Put this process in a kill-on-close job, so its children die with it.

    The job handle is deliberately never closed: it must live exactly as long
    as the process.

    Returns:
        True when the job is in place; False (with a warning) when it couldn't be
        set up or this isn't Windows. The daemon still runs either way.
    """
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return _warn("CreateJobObjectW")
    limits = _ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    is_set = kernel32.SetInformationJobObject(
        wintypes.HANDLE(job),
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    )
    if not is_set:
        return _warn("SetInformationJobObject")
    if not kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(job), wintypes.HANDLE(kernel32.GetCurrentProcess())
    ):
        return _warn("AssignProcessToJobObject")
    logger.info("Daemon is in a kill-on-close job; its sessions die with it")
    return True


def _warn(call: str) -> bool:
    """Log a failed Win32 call with its error and report failure."""
    logger.warning(
        "%s failed (%s); a hard daemon crash may leave claude.exe processes running",
        call,
        ctypes.WinError(ctypes.get_last_error()),
    )
    return False
