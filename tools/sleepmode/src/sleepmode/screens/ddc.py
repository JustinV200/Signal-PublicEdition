"""DDC/CI monitor power (VCP 0xD6) through the Windows dxva2 API, via ctypes. No admin needed.

Each HMONITOR maps to one or more physical monitors (usually one). Reads and writes
go to all of them. A monitor that doesn't speak DDC/CI (or has it switched off in its
on-screen menu) fails with an ERROR_GRAPHICS_* code, raised as DdcError.
"""

import contextlib
import ctypes
from collections.abc import Iterator
from ctypes import wintypes

POWER_MODE_VCP = 0xD6
# VCP 0xD6 values (MCCS): 1 on, 2 standby, 3 suspend, 4 DPM off, 5 power off.
POWER_ON = 1
POWER_OFF_MODES = range(2, 6)


class DdcError(OSError):
    """A DDC/CI call failed: the monitor doesn't answer, or refused the command."""


class _PhysicalMonitor(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


def read_power_mode(hmonitor: int) -> int:
    """Read VCP 0xD6 from the display's (first) physical monitor.

    Args:
        hmonitor: The display's HMONITOR (signal_displays.Monitor.handle).

    Returns:
        The current power mode (POWER_ON is 1).

    Raises:
        DdcError: The monitor didn't answer.
        ctypes.ArgumentError: hmonitor isn't a handle ctypes can pass.
    """
    dxva2 = _dxva2()
    with _physical_monitors(dxva2, hmonitor) as monitors:
        kind, current, maximum = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        if not dxva2.GetVCPFeatureAndVCPFeatureReply(
            monitors[0].hPhysicalMonitor,
            POWER_MODE_VCP,
            ctypes.byref(kind),
            ctypes.byref(current),
            ctypes.byref(maximum),
        ):
            raise _ddc_error("reading the power mode")
        return current.value


def set_power_mode(hmonitor: int, value: int) -> None:
    """Write VCP 0xD6 to every physical monitor of the display.

    Args:
        hmonitor: The display's HMONITOR.
        value: The power mode, e.g. POWER_ON or 4 (DPM off).

    Raises:
        DdcError: A monitor didn't accept the write. Acceptance doesn't mean it obeyed:
            DDC/CI writes get no reply, so only read_power_mode can confirm.
        ctypes.ArgumentError: hmonitor isn't a handle ctypes can pass.
    """
    dxva2 = _dxva2()
    with _physical_monitors(dxva2, hmonitor) as monitors:
        for monitor in monitors:
            if not dxva2.SetVCPFeature(monitor.hPhysicalMonitor, POWER_MODE_VCP, value):
                raise _ddc_error(f"setting the power mode to {value}")


def _dxva2() -> ctypes.WinDLL:
    """dxva2 with the signatures this file calls (64-bit handles need explicit types)."""
    dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)
    monitor_array = ctypes.POINTER(_PhysicalMonitor)
    dword_out = ctypes.POINTER(wintypes.DWORD)
    signatures = {
        "GetNumberOfPhysicalMonitorsFromHMONITOR": [wintypes.HMONITOR, dword_out],
        "GetPhysicalMonitorsFromHMONITOR": [wintypes.HMONITOR, wintypes.DWORD, monitor_array],
        "DestroyPhysicalMonitors": [wintypes.DWORD, monitor_array],
        # The VCP code is a BYTE; wintypes.BYTE is signed, and 0xD6 needs unsigned.
        "GetVCPFeatureAndVCPFeatureReply": [
            wintypes.HANDLE,
            ctypes.c_ubyte,
            dword_out,
            dword_out,
            dword_out,
        ],
        "SetVCPFeature": [wintypes.HANDLE, ctypes.c_ubyte, wintypes.DWORD],
    }
    for name, argtypes in signatures.items():
        function = getattr(dxva2, name)
        function.argtypes = argtypes
        function.restype = wintypes.BOOL
    return dxva2


@contextlib.contextmanager
def _physical_monitors(dxva2: ctypes.WinDLL, hmonitor: int) -> Iterator[ctypes.Array]:
    """Open the display's physical monitor handles, and always release them."""
    count = wintypes.DWORD()
    if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, ctypes.byref(count)):
        raise _ddc_error("finding the physical monitor")
    if count.value == 0:
        raise DdcError("the display has no physical monitor to talk to")
    monitors = (_PhysicalMonitor * count.value)()
    if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count, monitors):
        raise _ddc_error("opening the physical monitor")
    try:
        yield monitors
    finally:
        dxva2.DestroyPhysicalMonitors(count, monitors)


def _ddc_error(action: str) -> DdcError:
    # Last-error values are HRESULT-style ERROR_GRAPHICS_* codes; show them unsigned.
    code = ctypes.get_last_error() & 0xFFFFFFFF
    return DdcError(f"DDC/CI failed {action} (error {code:#010x})")
