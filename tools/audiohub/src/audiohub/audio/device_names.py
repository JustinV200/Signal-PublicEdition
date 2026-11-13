"""Heuristics over raw PortAudio device names, used by device listing and lookup.

Two jobs, both purely about reading names:
- `friendly_device_name` expands the unexpanded Windows resource strings that
  WDM-KS reports for some Bluetooth endpoints.
- `bluetooth_hints` guesses which devices belong to a Bluetooth headset (such
  as the user's glasses) and which of those are Hands-Free (HFP) endpoints.
  Windows exposes no flag for this, so it works from naming conventions.
"""

import re
from collections.abc import Iterable
from typing import Protocol

HANDS_FREE = "hands-free"
BLUETOOTH = "bluetooth"

# Matches e.g. 'Headset (@System32\drivers\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(BT-Glasses-01))'
# which Windows itself displays as 'Headset (BT-Glasses-01 Hands-Free)'.
_RESOURCE_NAME = re.compile(
    r"^(?P<prefix>.*?)\(@[^;]*;(?P<template>[^\r\n]*?)(?:%0)?\r?\n;\((?P<argument>[^()]*)\)\)$"
)

# Name fragments Windows uses for Bluetooth Hands-Free (HFP) endpoints.
_HANDS_FREE_MARKERS = ("hands-free", "handsfree", "hands free", "ag audio")
# Windows names a Bluetooth HFP endpoint "Headset (<device>)". Wired USB headsets
# use "Headset Microphone (...)" / "Headset Earphone (...)" instead.
_HANDS_FREE_PREFIX = "headset ("
_BLUETOOTH_MARKERS = ("bluetooth",)
# Removed from a device's parenthesised label so a headset's Hands-Free and
# stereo endpoints reduce to the same label, e.g. "bt-glasses-01".
_LABEL_NOISE = (*_HANDS_FREE_MARKERS, "stereo")


class _NamedDevice(Protocol):
    index: int
    name: str


def friendly_device_name(raw_name: str) -> str:
    """Return a readable device name.

    Expands WDM-KS resource-string names and collapses stray whitespace
    (including the CR/LF those strings contain). Other names pass through.

    Args:
        raw_name: The name exactly as PortAudio reports it.

    Returns:
        The cleaned name.
    """
    match = _RESOURCE_NAME.match(raw_name)
    if match is None:
        return " ".join(raw_name.split())
    expanded = match["template"].replace("%1", match["argument"])
    return f"{match['prefix']}({' '.join(expanded.split())})"


def bluetooth_hints(devices: Iterable[_NamedDevice]) -> dict[int, str]:
    """Guess which devices are Bluetooth headset endpoints.

    A device is HANDS_FREE if its name carries a Hands-Free marker. Any other
    device is BLUETOOTH if its name says so, or if its parenthesised label
    matches a Hands-Free device's label (the same headset's stereo endpoint).

    Args:
        devices: Objects with `index` and `name`, e.g. `DeviceInfo`.

    Returns:
        Mapping of device index to HANDS_FREE or BLUETOOTH. Devices that don't
        look like Bluetooth are absent.
    """
    devices = list(devices)
    hints = {device.index: HANDS_FREE for device in devices if _is_hands_free(device.name)}
    headset_labels = {_device_label(device.name) for device in devices if device.index in hints}
    headset_labels.discard("")
    for device in devices:
        if device.index in hints:
            continue
        is_named_bluetooth = any(marker in device.name.casefold() for marker in _BLUETOOTH_MARKERS)
        if is_named_bluetooth or _device_label(device.name) in headset_labels:
            hints[device.index] = BLUETOOTH
    return hints


def _is_hands_free(name: str) -> bool:
    folded = name.casefold()
    return folded.startswith(_HANDS_FREE_PREFIX) or any(
        marker in folded for marker in _HANDS_FREE_MARKERS
    )


def _device_label(name: str) -> str:
    # 'Headphones (BT-Glasses-01 Stereo)' -> 'bt-glasses-01'. MME truncates names to
    # 31 characters, so a missing closing parenthesis is tolerated.
    start = name.find("(")
    if start == -1:
        return ""
    label = name[start + 1 :].removesuffix(")").casefold()
    for noise in _LABEL_NOISE:
        label = label.replace(noise, " ")
    return " ".join(label.split())
