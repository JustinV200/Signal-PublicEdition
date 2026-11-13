"""List the attached monitors and pick the projector (ctypes EnumDisplayMonitors + GetMonitorInfoW).

Lifted from tools/whiteboard (whiteboard.display.screen.monitors) so other tools find
the projector the same way; the only addition is Monitor.handle (the HMONITOR).
Bounds are physical desktop pixels: enumeration runs with a per-monitor-DPI-aware
thread context, so a scaled primary display doesn't distort the projector's position.
Each monitor also carries its Windows display scale (GetDpiForMonitor). The board's
"projector pixels" are the logical size, physical / scale: a 1920x1080 projector at
150% is a 1280x720 CSS-pixel page.
"""

import contextlib
import ctypes
import logging
from collections.abc import Iterator
from ctypes import wintypes
from dataclasses import dataclass

from signal_displays.friendly_names import friendly_names

log = logging.getLogger(__name__)

MONITORINFOF_PRIMARY = 0x1
MDT_EFFECTIVE_DPI = 0
BASE_DPI = 96
# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, a pseudo-handle defined as ((HANDLE)-4).
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

_MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class ProjectorNotFoundError(LookupError):
    """Raised when no monitor matches the configured name and there's no non-primary display."""


@dataclass(frozen=True)
class Monitor:
    """One display: its `\\\\.\\DISPLAYn` name, EDID friendly name, physical bounds and scale.

    `handle` is the HMONITOR from enumeration (0 when built by hand, e.g. in tests). It is
    only valid until the display layout changes, so use it right after list_monitors.
    """

    device_name: str
    friendly_name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool
    scale: float = 1.0
    handle: int = 0

    @property
    def logical_size(self) -> tuple[int, int]:
        """(width, height) in logical pixels, i.e. CSS pixels of a fullscreen page on it."""
        return round(self.width / self.scale), round(self.height / self.scale)


def list_monitors() -> list[Monitor]:
    """List every attached monitor with its physical-pixel desktop bounds.

    Friendly names are best-effort: if the display-config API fails, they're
    empty strings and a warning is logged.

    Raises:
        OSError: If EnumDisplayMonitors or GetMonitorInfoW fails.
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    handles: list[int] = []

    def collect(handle: int, _hdc: int, _rect: object, _data: int) -> bool:
        handles.append(handle)
        return True

    callback = _MonitorEnumProc(collect)
    with _per_monitor_dpi(user32):
        if not user32.EnumDisplayMonitors(None, None, callback, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        infos = [_monitor_info(user32, handle) for handle in handles]
        scales = [_monitor_scale(handle) for handle in handles]
    try:
        names = friendly_names()
    except OSError as error:
        log.warning("monitor friendly names unavailable: %s", error)
        names = {}
    return [
        _to_monitor(info, names.get(info.szDevice, ""), scale, handle)
        for info, scale, handle in zip(infos, scales, handles, strict=True)
    ]


def pick_projector(monitors: list[Monitor], name_match: str) -> Monitor:
    """Choose the projector: a case-insensitive name match, else the first non-primary display.

    Args:
        monitors: From list_monitors.
        name_match: Substring of the friendly name or the device name; "" skips matching.

    Raises:
        ProjectorNotFoundError: If nothing matches and every display is primary.
    """
    needle = name_match.lower()
    if needle:
        for monitor in monitors:
            if needle in monitor.friendly_name.lower() or needle in monitor.device_name.lower():
                return monitor
    for monitor in monitors:
        if not monitor.is_primary:
            log.info("no monitor matches %r; using non-primary %s", name_match, monitor.device_name)
            return monitor
    raise ProjectorNotFoundError(
        f"no projector found: nothing matches {name_match!r} and there is no second display. "
        "Is the projector on and set to extend the desktop?"
    )


def find_projector(name_match: str) -> Monitor:
    """Find the projector on this machine (list_monitors + pick_projector).

    Raises:
        ProjectorNotFoundError: If there is no matching or non-primary display.
        OSError: If monitor enumeration fails.
    """
    return pick_projector(list_monitors(), name_match)


@contextlib.contextmanager
def _per_monitor_dpi(user32: ctypes.WinDLL) -> Iterator[None]:
    # Thread-scoped, so the rest of the process keeps its own DPI awareness.
    set_context = user32.SetThreadDpiAwarenessContext
    set_context.restype = ctypes.c_void_p
    set_context.argtypes = [ctypes.c_void_p]
    previous = set_context(_PER_MONITOR_AWARE_V2)
    try:
        yield
    finally:
        if previous:
            set_context(previous)


def _monitor_info(user32: ctypes.WinDLL, handle: int) -> _MonitorInfoEx:
    info = _MonitorInfoEx()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(wintypes.HMONITOR(handle), ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info


def _monitor_scale(handle: int) -> float:
    dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
    result = ctypes.WinDLL("shcore").GetDpiForMonitor(
        wintypes.HMONITOR(handle), MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
    )
    if result != 0:
        raise OSError(f"GetDpiForMonitor failed with HRESULT {result:#x}")
    return dpi_x.value / BASE_DPI


def _to_monitor(info: _MonitorInfoEx, friendly_name: str, scale: float, handle: int) -> Monitor:
    rect = info.rcMonitor
    return Monitor(
        device_name=info.szDevice,
        friendly_name=friendly_name,
        x=rect.left,
        y=rect.top,
        width=rect.right - rect.left,
        height=rect.bottom - rect.top,
        is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
        scale=scale,
        handle=handle,
    )
