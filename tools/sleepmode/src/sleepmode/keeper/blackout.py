"""BlackoutWindows: borderless, topmost black windows covering displays that can't be powered off.

Used for monitors without DDC/CI, and for the projector when the whiteboard can't show
its night view. The windows hide the mouse pointer, have no taskbar button, and live
in the keeper process, whose loop pumps their messages (sleepmode.keeper.message_loop).
They vanish with the keeper, so any wake (or a crash) clears them. The window class
is registered once per process, so the keeper can hold more than one set (the
projector's own window comes and goes with the night view; see night_guard).
"""

import ctypes
import functools
import logging
from collections.abc import Sequence
from ctypes import wintypes

log = logging.getLogger(__name__)

CLASS_NAME = "SignalSleepmodeBlackout"
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080  # no taskbar or Alt+Tab entry
WM_SETCURSOR = 0x0020
BLACK_BRUSH = 4
# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, ((HANDLE)-4): window rects in physical pixels.
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

_LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(
    _LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class _WndClass(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class BlackoutWindows:
    """The keeper's black windows, one per rect."""

    def __init__(self, rects: Sequence[tuple[int, int, int, int]]) -> None:
        """Open a black window over each rect (physical desktop pixels: x, y, width, height).

        Raises:
            OSError: The window class or a window couldn't be created.
        """
        self._user32 = _user32()
        self._hwnds: list[int] = []
        if not rects:
            return
        instance = _register_class()
        try:
            for x, y, width, height in rects:
                self._hwnds.append(self._create_window(instance, x, y, width, height))
        except OSError:
            # Nobody gets this object to close, and the keeper now wakes everything.
            self.close()
            raise
        log.info("black windows up on %d display(s)", len(self._hwnds))

    def close(self) -> None:
        """Destroy every window. Safe to call twice."""
        for hwnd in self._hwnds:
            self._user32.DestroyWindow(hwnd)
        self._hwnds.clear()

    def _create_window(self, instance: int, x: int, y: int, width: int, height: int) -> int:
        hwnd = self._user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            CLASS_NAME,
            "Sleep mode",
            WS_POPUP | WS_VISIBLE,
            x,
            y,
            width,
            height,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        return hwnd


@functools.cache
def _register_class() -> int:
    """Register the window class, once per process; returns the module instance handle.

    Raises:
        OSError: RegisterClassW failed (the cache then retries on the next call).
    """
    user32 = _user32()
    # The keeper is its own process, so a process-wide DPI setting is fine here.
    if not user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2):
        # Without it Windows scales the rects, so a window may not fit its display.
        log.warning(
            "couldn't make the keeper per-monitor DPI aware (%s); black windows may "
            "not cover their displays exactly",
            ctypes.WinError(ctypes.get_last_error()),
        )
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    instance = kernel32.GetModuleHandleW(None)
    window_class = _WndClass()
    window_class.lpfnWndProc = _WINDOW_PROC
    window_class.hInstance = instance
    gdi32 = ctypes.WinDLL("gdi32")
    gdi32.GetStockObject.restype = wintypes.HGDIOBJ
    window_class.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
    window_class.lpszClassName = CLASS_NAME
    # hCursor stays NULL and WM_SETCURSOR clears it, so no pointer shows over the black.
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError(ctypes.get_last_error())
    return instance


def _window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    """The black windows' window procedure: no pointer, the rest left to Windows."""
    if message == WM_SETCURSOR:
        _user32().SetCursor(None)
        return 1
    return _user32().DefWindowProcW(hwnd, message, wparam, lparam)


# Module-level, so ctypes never frees the callback while a window of the class exists.
_WINDOW_PROC = _WNDPROC(_window_proc)


@functools.cache
def _user32() -> ctypes.WinDLL:
    """user32 with the signatures this file calls (64-bit handles need explicit types)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = _LRESULT
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WndClass)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.SetCursor.argtypes = [wintypes.HANDLE]
    user32.SetCursor.restype = wintypes.HANDLE
    return user32
