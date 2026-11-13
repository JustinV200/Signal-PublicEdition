"""Bring the Windows Hello prompt to the foreground while the vault waits for it.

A Hello prompt raised from an unpackaged console process often opens behind
other windows. KeePassXC works around this by finding the prompt's host window
("Credential Dialog Xaml Host") and calling SetForegroundWindow; this does the
same from a short-lived background thread. It's best effort: if Windows refuses
the focus change, the owner can still click the prompt in the taskbar.
"""

import ctypes
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes

HELLO_PROMPT_WINDOW_CLASS = "Credential Dialog Xaml Host"
POLL_INTERVAL_S = 0.1
# Give up looking after this long; the prompt normally appears within a second.
SEARCH_TIMEOUT_S = 10.0


def _user32() -> ctypes.WinDLL:
    """Load user32 with HWND-correct signatures (the default int return would truncate)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    return user32


def _focus_when_found(stop: threading.Event) -> None:
    """Poll for the Hello prompt window and focus it once, until `stop` is set or time runs out."""
    user32 = _user32()
    waited_s = 0.0
    while not stop.is_set() and waited_s < SEARCH_TIMEOUT_S:
        window = user32.FindWindowW(HELLO_PROMPT_WINDOW_CLASS, None)
        if window:
            user32.SetForegroundWindow(window)
            return
        stop.wait(POLL_INTERVAL_S)
        waited_s += POLL_INTERVAL_S


@contextmanager
def hello_prompt_in_front() -> Iterator[None]:
    """While the body runs, try to bring the Hello prompt to the front."""
    stop = threading.Event()
    worker = threading.Thread(target=_focus_when_found, args=(stop,), daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
