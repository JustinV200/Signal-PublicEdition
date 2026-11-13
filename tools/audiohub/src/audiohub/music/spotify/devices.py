"""Pick a Spotify Connect device to wake when the account has no active one.

An open but idle Spotify app is listed by `GET /me/player/devices` but isn't
"active", so player commands without a device_id fail with NO_ACTIVE_DEVICE.
Sending the command again with that device's id wakes it.
"""

from typing import Any

# Spotify's device type for the desktop app, preferred over phones and speakers
# because audiohub runs on, and ducks audio on, this PC.
COMPUTER_DEVICE_TYPE = "computer"


def pick_device_id(devices_response: dict[str, Any] | None, hostname: str = "") -> str | None:
    """Return the id of the best device to wake, or None if none is usable.

    Restricted devices (which reject Web API commands) and devices without an
    id are skipped. Preference: the device named like `hostname` (this PC,
    case-insensitive), then any "Computer", then the first one listed.

    Args:
        devices_response: The `GET /me/player/devices` body, from the network.
        hostname: This machine's hostname; empty matches nothing.
    """
    listed = devices_response.get("devices") if isinstance(devices_response, dict) else None
    usable = [
        device
        for device in listed or []
        if isinstance(device, dict)
        and isinstance(device.get("id"), str)
        and not device.get("is_restricted")
    ]
    wanted = hostname.strip().lower()
    for device in usable:
        if wanted and str(device.get("name", "")).strip().lower() == wanted:
            return device["id"]
    for device in usable:
        if str(device.get("type", "")).lower() == COMPUTER_DEVICE_TYPE:
            return device["id"]
    return usable[0]["id"] if usable else None
