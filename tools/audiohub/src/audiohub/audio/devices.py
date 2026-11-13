"""Sound device discovery and lookup on top of sounddevice (PortAudio).

`list_devices` gives a typed snapshot of every device, and `resolve_device`
turns a config/CLI device spec (name substring, index, or None) into the
PortAudio index that Microphone and Speaker open.
"""

from dataclasses import dataclass
from typing import Literal

import sounddevice as sd

from audiohub.audio.device_names import friendly_device_name

DeviceKind = Literal["input", "output"]

WASAPI_HOSTAPI = "Windows WASAPI"

# Host APIs searched when a device is given by name, best first. WASAPI opens
# shared-mode streams at the endpoint's native rate; MME is the universal
# fallback. DirectSound and WDM-KS devices are only used when given by index.
PREFERRED_HOSTAPIS: tuple[str, ...] = (WASAPI_HOSTAPI, "MME")


class DeviceNotFoundError(LookupError):
    """Raised when a device spec matches no usable input or output device."""


@dataclass(frozen=True)
class DeviceInfo:
    """One PortAudio device as reported by sounddevice.

    `is_default_input`/`is_default_output` mean the default of this device's
    own host API, so the Windows default endpoint is marked once per host API.
    """

    index: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_default_input: bool
    is_default_output: bool

    def supports(self, kind: DeviceKind) -> bool:
        """Return True if the device has at least one channel of the given kind."""
        channels = self.max_input_channels if kind == "input" else self.max_output_channels
        return channels > 0


def list_devices() -> list[DeviceInfo]:
    """Return every PortAudio device, in PortAudio index order.

    Names are cleaned with `friendly_device_name`.

    Raises:
        sounddevice.PortAudioError: If PortAudio cannot enumerate devices.
    """
    hostapis = sd.query_hostapis()
    devices: list[DeviceInfo] = []
    for raw in sd.query_devices():
        hostapi = hostapis[raw["hostapi"]]
        devices.append(
            DeviceInfo(
                index=raw["index"],
                name=friendly_device_name(raw["name"]),
                hostapi=hostapi["name"],
                max_input_channels=raw["max_input_channels"],
                max_output_channels=raw["max_output_channels"],
                default_samplerate=raw["default_samplerate"],
                is_default_input=raw["index"] == hostapi["default_input_device"],
                is_default_output=raw["index"] == hostapi["default_output_device"],
            )
        )
    return devices


def resolve_device(spec: str | int | None, kind: DeviceKind) -> int | None:
    """Turn a device spec into a PortAudio device index.

    Args:
        spec: None for the system default, an int device index, or a
            case-insensitive name substring. A name is looked up under
            PREFERRED_HOSTAPIS only, preferring WASAPI, then an exact name
            match, then the lowest index.
        kind: Whether the device will be used for "input" or "output".

    Returns:
        The device index, or None for the system default.

    Raises:
        DeviceNotFoundError: If the index doesn't exist or lacks channels of
            `kind`, or if no preferred-host-API device name contains `spec`.
    """
    if spec is None:
        return None
    devices = list_devices()
    # bool is an int subclass; True/False are never meant as device indexes.
    if isinstance(spec, int) and not isinstance(spec, bool):
        return _resolve_index(spec, kind, devices)
    return _resolve_name(str(spec), kind, devices)


def _resolve_index(index: int, kind: DeviceKind, devices: list[DeviceInfo]) -> int:
    device = next((candidate for candidate in devices if candidate.index == index), None)
    if device is None:
        raise DeviceNotFoundError(f"no sound device has index {index}; run `audiohub devices`")
    if not device.supports(kind):
        raise DeviceNotFoundError(f"device {index} ({device.name}) is not an {kind} device")
    return index


def _resolve_name(name: str, kind: DeviceKind, devices: list[DeviceInfo]) -> int:
    needle = name.strip().casefold()
    if not needle:
        raise DeviceNotFoundError(f"empty {kind} device name")
    candidates = [
        device
        for device in devices
        if device.supports(kind)
        and device.hostapi in PREFERRED_HOSTAPIS
        and needle in device.name.casefold()
    ]
    if not candidates:
        hostapis = " or ".join(PREFERRED_HOSTAPIS)
        raise DeviceNotFoundError(
            f"no {kind} device under {hostapis} has a name containing {name!r}; "
            "run `audiohub devices --all`"
        )
    best = min(
        candidates,
        key=lambda device: (
            PREFERRED_HOSTAPIS.index(device.hostapi),
            device.name.casefold() != needle,
            device.index,
        ),
    )
    return best.index
