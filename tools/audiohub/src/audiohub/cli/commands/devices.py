"""`audiohub devices`: list sound devices, marking defaults and likely Bluetooth endpoints.

Lists WASAPI and MME devices (the host APIs audiohub picks by name), or every
host API with --all. Then it shows what the configured input/output device
specs resolve to, so a config or --*-device flag can be checked before use.
"""

import argparse
from collections.abc import Sequence
from typing import TYPE_CHECKING

from audiohub.cli.command import Command
from audiohub.config import Settings

if TYPE_CHECKING:
    from audiohub.audio import DeviceInfo, DeviceKind

# audiohub.audio (sounddevice, numpy: ~0.4 s) is imported inside the functions
# that use it: every `audiohub` command imports this module through the registry.

EXIT_OK = 0
EXIT_UNRESOLVED_DEVICE = 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the `devices` options."""
    parser.add_argument(
        "--all",
        dest="show_all",
        action="store_true",
        help="also list DirectSound and WDM-KS devices",
    )


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Print the device list and the configured devices.

    Returns:
        0, or 1 if a configured device spec doesn't resolve.
    """
    from audiohub.audio import bluetooth_hints, list_devices

    devices = list_devices()
    hints = bluetooth_hints(devices)
    for hostapi in _hostapis_to_show(devices, args.show_all):
        print(hostapi)
        for device in devices:
            if device.hostapi == hostapi:
                print(format_device_line(device, hints.get(device.index)))
        print()
    if not args.show_all and _has_only_hidden_bluetooth(devices, hints):
        print(
            "Bluetooth endpoints appear only under other host APIs, so the headset is\n"
            "probably paired but not connected. Run `audiohub devices --all` to see them.\n"
        )
    print("Configured devices (config file + flags):")
    input_ok = _print_resolution("input", settings.audio.input_device, devices)
    output_ok = _print_resolution("output", settings.audio.output_device, devices)
    return EXIT_OK if input_ok and output_ok else EXIT_UNRESOLVED_DEVICE


def format_device_line(device: "DeviceInfo", hint: str | None) -> str:
    """Format one device as an indented table row with its markers.

    Args:
        device: The device to describe.
        hint: Its Bluetooth hint ("hands-free"/"bluetooth"), or None.

    Returns:
        e.g. "   15  in   2ch  48000 Hz  Microphone (USB)  [default input]"
    """
    if device.max_input_channels and device.max_output_channels:
        direction = "in/out"
        channels = f"{device.max_input_channels}+{device.max_output_channels}ch"
    elif device.max_input_channels:
        direction, channels = "in", f"{device.max_input_channels}ch"
    else:
        direction, channels = "out", f"{device.max_output_channels}ch"
    markers = _device_markers(device, hint)
    marker_text = f"  [{', '.join(markers)}]" if markers else ""
    rate = f"{device.default_samplerate:.0f} Hz"
    columns = f"{device.index:>3}  {direction:<6} {channels:>5}  {rate:>8}"
    return f"  {columns}  {device.name}{marker_text}"


def _device_markers(device: "DeviceInfo", hint: str | None) -> list[str]:
    markers = []
    if device.is_default_input:
        markers.append("default input")
    if device.is_default_output:
        markers.append("default output")
    if hint:
        markers.append(hint)
    return markers


def _hostapis_to_show(devices: Sequence["DeviceInfo"], show_all: bool) -> list[str]:
    from audiohub.audio import PREFERRED_HOSTAPIS

    present = list(dict.fromkeys(device.hostapi for device in devices))
    preferred = [hostapi for hostapi in PREFERRED_HOSTAPIS if hostapi in present]
    if not show_all:
        return preferred
    return preferred + [hostapi for hostapi in present if hostapi not in preferred]


def _has_only_hidden_bluetooth(devices: Sequence["DeviceInfo"], hints: dict[int, str]) -> bool:
    from audiohub.audio import PREFERRED_HOSTAPIS

    hinted_hostapis = {device.hostapi for device in devices if device.index in hints}
    return bool(hinted_hostapis) and not hinted_hostapis & set(PREFERRED_HOSTAPIS)


def _print_resolution(
    kind: "DeviceKind", spec: str | int | None, devices: Sequence["DeviceInfo"]
) -> bool:
    from audiohub.audio import DeviceNotFoundError, resolve_device

    label = f"  {kind}:".ljust(10)
    if spec is None:
        print(f"{label}system default")
        return True
    try:
        index = resolve_device(spec, kind)
    except DeviceNotFoundError as error:
        print(f"{label}{spec!r} -> NOT FOUND: {error}")
        return False
    device = next(device for device in devices if device.index == index)
    print(f"{label}{spec!r} -> {index} {device.name} ({device.hostapi})")
    return True


COMMAND = Command(
    name="devices",
    help="list sound devices, marking defaults and likely Bluetooth/Hands-Free endpoints",
    add_arguments=add_arguments,
    run=run,
)
