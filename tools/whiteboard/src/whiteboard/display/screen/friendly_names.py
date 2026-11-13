"""Monitor friendly names ("PROJ-1 TV") keyed by GDI device name ("\\\\.\\DISPLAY1"), via ctypes.

EnumDisplayMonitors only knows GDI device names. The EDID friendly name comes
from the display-config API: QueryDisplayConfig lists the active paths, and
DisplayConfigGetDeviceInfo names each path's source (GDI name) and target (monitor).
Struct layouts follow wingdi.h.
"""

import ctypes
from ctypes import wintypes

QDC_ONLY_ACTIVE_PATHS = 0x2
GET_SOURCE_NAME = 1
GET_TARGET_NAME = 2
ERROR_SUCCESS = 0
ERROR_INSUFFICIENT_BUFFER = 122
# The display config can change between the size query and the fetch; retry a few times.
_QUERY_ATTEMPTS = 3


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _PathSourceInfo(ctypes.Structure):
    _fields_ = [
        ("adapterId", _Luid),
        ("id", ctypes.c_uint32),
        ("modeInfoIdx", ctypes.c_uint32),
        ("statusFlags", ctypes.c_uint32),
    ]


class _PathTargetInfo(ctypes.Structure):
    _fields_ = [
        ("adapterId", _Luid),
        ("id", ctypes.c_uint32),
        ("modeInfoIdx", ctypes.c_uint32),
        ("outputTechnology", ctypes.c_uint32),
        ("rotation", ctypes.c_uint32),
        ("scaling", ctypes.c_uint32),
        ("refreshNumerator", ctypes.c_uint32),
        ("refreshDenominator", ctypes.c_uint32),
        ("scanLineOrdering", ctypes.c_uint32),
        ("targetAvailable", wintypes.BOOL),
        ("statusFlags", ctypes.c_uint32),
    ]


class _PathInfo(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", _PathSourceInfo),
        ("targetInfo", _PathTargetInfo),
        ("flags", ctypes.c_uint32),
    ]


class _ModeInfo(ctypes.Structure):
    # Only the size matters here (64 bytes); the 48-byte union is never read.
    _fields_ = [
        ("infoType", ctypes.c_uint32),
        ("id", ctypes.c_uint32),
        ("adapterId", _Luid),
        ("union", ctypes.c_byte * 48),
    ]


class _InfoHeader(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("adapterId", _Luid),
        ("id", ctypes.c_uint32),
    ]


class _SourceName(ctypes.Structure):
    _fields_ = [("header", _InfoHeader), ("viewGdiDeviceName", wintypes.WCHAR * 32)]


class _TargetName(ctypes.Structure):
    _fields_ = [
        ("header", _InfoHeader),
        ("flags", ctypes.c_uint32),
        ("outputTechnology", ctypes.c_uint32),
        ("edidManufactureId", ctypes.c_uint16),
        ("edidProductCodeId", ctypes.c_uint16),
        ("connectorInstance", ctypes.c_uint32),
        ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128),
    ]


def friendly_names() -> dict[str, str]:
    """Map each active display's GDI device name to its monitor's friendly name.

    Returns:
        e.g. `{"\\\\.\\DISPLAY1": "PROJ-1 TV"}`. A monitor without an EDID name maps to "".

    Raises:
        OSError: If a display-config call fails.
    """
    user32 = ctypes.WinDLL("user32")
    names: dict[str, str] = {}
    for path in _active_paths(user32):
        source = _SourceName()
        _fill_header(source.header, GET_SOURCE_NAME, ctypes.sizeof(source), path.sourceInfo)
        _get_device_info(user32, source.header)
        target = _TargetName()
        _fill_header(target.header, GET_TARGET_NAME, ctypes.sizeof(target), path.targetInfo)
        _get_device_info(user32, target.header)
        names[source.viewGdiDeviceName] = target.monitorFriendlyDeviceName
    return names


def _active_paths(user32: ctypes.WinDLL) -> list[_PathInfo]:
    for _ in range(_QUERY_ATTEMPTS):
        path_count, mode_count = ctypes.c_uint32(), ctypes.c_uint32()
        _check(
            user32.GetDisplayConfigBufferSizes(
                QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), ctypes.byref(mode_count)
            ),
            "GetDisplayConfigBufferSizes",
        )
        paths = (_PathInfo * path_count.value)()
        modes = (_ModeInfo * mode_count.value)()
        result = user32.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(path_count),
            paths,
            ctypes.byref(mode_count),
            modes,
            None,
        )
        if result != ERROR_INSUFFICIENT_BUFFER:
            _check(result, "QueryDisplayConfig")
            return list(paths[: path_count.value])
    raise OSError("QueryDisplayConfig kept changing size; displays are being reconfigured")


def _fill_header(
    header: _InfoHeader, info_type: int, size: int, path_part: ctypes.Structure
) -> None:
    header.type = info_type
    header.size = size
    header.adapterId = path_part.adapterId
    header.id = path_part.id


def _get_device_info(user32: ctypes.WinDLL, header: _InfoHeader) -> None:
    _check(user32.DisplayConfigGetDeviceInfo(ctypes.byref(header)), "DisplayConfigGetDeviceInfo")


def _check(result: int, call: str) -> None:
    if result != ERROR_SUCCESS:
        raise OSError(f"{call} failed with Win32 error {result}")
