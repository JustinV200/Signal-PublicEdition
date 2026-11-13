"""The keeper thread's message loop, shared by the black windows and the input hooks.

Windows hands both the black windows' messages and the low-level keyboard and mouse
hook calls to the thread that made them, and only while that thread pumps messages.
The keeper waits with MsgWaitForMultipleObjectsEx rather than sleeping, so a hook call
runs at once: Windows silently removes a low-level hook whose call waits longer than
LowLevelHooksTimeout, and a removed hook would stop real input waking sleep mode.
"""

import ctypes
import functools
from ctypes import wintypes

PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF  # any message, input, paint, timer or sent message (hook calls)
MWMO_INPUTAVAILABLE = 0x0004  # also return for input already queued, not just new input
WAIT_FAILED = 0xFFFFFFFF


def pump_messages() -> None:
    """Handle everything waiting for this thread: window messages and input hook calls."""
    user32 = _user32()
    message = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))


def wait_for_messages(timeout_s: float) -> None:
    """Block until something arrives for pump_messages, or timeout_s passes.

    Args:
        timeout_s: The longest wait, in seconds.

    Raises:
        OSError: The wait failed.
    """
    timeout_ms = round(timeout_s * 1000)
    result = _user32().MsgWaitForMultipleObjectsEx(
        0, None, timeout_ms, QS_ALLINPUT, MWMO_INPUTAVAILABLE
    )
    if result == WAIT_FAILED:
        raise ctypes.WinError(ctypes.get_last_error())


@functools.cache
def _user32() -> ctypes.WinDLL:
    """user32 with the signatures this file calls (its own copy, so no other file's apply)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.MsgWaitForMultipleObjectsEx.argtypes = [
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    user32.MsgWaitForMultipleObjectsEx.restype = wintypes.DWORD
    return user32
