"""idle_ms: how long since the last keyboard or mouse input anywhere on this PC.

GetLastInputInfo gives the tick count of the last input, GetTickCount the tick
count now; both are 32-bit and wrap every 49.7 days, so the difference is taken
mod 2^32. Input is system-wide and synthetic input counts too, which is why callers
only trust a short window right before a prompt (see tools/brief's prompt hook).
"""

import ctypes
from ctypes import wintypes

TICK_WRAP = 2**32


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_ms() -> int:
    """Milliseconds since the last input event.

    Raises:
        OSError: GetLastInputInfo failed.
    """
    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetTickCount.restype = wintypes.DWORD
    info = _LastInputInfo(cbSize=ctypes.sizeof(_LastInputInfo))
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("GetLastInputInfo failed")
    return (kernel32.GetTickCount() - info.dwTime) % TICK_WRAP
