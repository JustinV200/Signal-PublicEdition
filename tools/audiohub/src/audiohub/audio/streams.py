"""Open, start and close the mono PortAudio streams used by Microphone and Speaker.

Why opening is more than one sounddevice call:
- PortAudio snapshots the device list when it initialises, and Windows
  renumbers devices when a Bluetooth headset reconnects. So each open first
  refreshes PortAudio (only while no audiohub stream is open, because
  Pa_Terminate kills open streams) and then re-resolves the device spec.
- Streams open at the device's reported native rate; audiohub resamples with
  soxr. WASAPI streams also get auto_convert, because a Bluetooth endpoint
  switches to 16 kHz Hands-Free when its mic opens while PortAudio still
  reports the old rate.
- Every failure becomes AudioStreamError naming the device.
"""

import threading
from collections.abc import Callable
from typing import Any

import sounddevice as sd

from audiohub.audio.devices import WASAPI_HOSTAPI, DeviceKind, resolve_device

# All audiohub audio is mono float32. PortAudio up/down-mixes mono to the
# endpoint's channel count itself.
STREAM_CHANNELS = 1
STREAM_DTYPE = "float32"

# Guards _open_streams and the refresh-then-open sequence.
_streams_lock = threading.Lock()
# Streams opened here and not yet closed; refreshing PortAudio would kill them.
_open_streams: set[Any] = set()


class AudioStreamError(RuntimeError):
    """Raised when a sound device can't be opened, started or kept playing."""


def open_mono_stream(
    kind: DeviceKind,
    device_spec: str | int | None,
    callback: Callable[..., None],
    finished_callback: Callable[[], None] | None = None,
) -> sd.InputStream | sd.OutputStream:
    """Resolve a device spec and create (but don't start) a mono float32 stream.

    Release the stream with `close_stream`, not `stream.close()`.

    Args:
        kind: "input" for an InputStream, "output" for an OutputStream.
        device_spec: Name substring, device index, or None for the default.
        callback: The PortAudio callback. It runs on PortAudio's audio thread.
        finished_callback: Called on the audio thread once the stream stops.
            It must return None.

    Returns:
        The opened stream. Its `samplerate` attribute is the native rate.

    Raises:
        DeviceNotFoundError: If `device_spec` matches no current device.
        AudioStreamError: If PortAudio can't be refreshed or refuses the device.
    """
    with _streams_lock:
        if not _open_streams:
            _refresh_portaudio()
        device_index = resolve_device(device_spec, kind)
        stream = _create_stream(kind, device_index, callback, finished_callback)
        _open_streams.add(stream)
    return stream


def start_stream(stream: sd.InputStream | sd.OutputStream) -> None:
    """Start a stream from `open_mono_stream`, closing it if it won't start.

    Raises:
        AudioStreamError: If PortAudio fails to start the stream.
    """
    try:
        stream.start()
    except sd.PortAudioError as error:
        close_stream(stream)
        raise AudioStreamError(f"could not start the audio stream: {error}") from error


def close_stream(stream: sd.InputStream | sd.OutputStream) -> None:
    """Close a stream from `open_mono_stream`. Closing twice is harmless."""
    with _streams_lock:
        _open_streams.discard(stream)
    # sounddevice ignores errors from closing an already-closed stream.
    stream.close()


def _refresh_portaudio() -> None:
    # sounddevice has no public re-scan; _terminate/_initialize are its own
    # init pair (pinned sounddevice version). Takes about 20 ms here.
    # If an earlier _initialize failed, PortAudio is already terminated
    # (_initialized == 0) and terminating again would fail on every later
    # open, leaving audio dead until restart. So only terminate when needed.
    try:
        if sd._initialized:
            sd._terminate()
        sd._initialize()
    except sd.PortAudioError as error:
        raise AudioStreamError(f"could not refresh the sound device list: {error}") from error


def _create_stream(
    kind: DeviceKind,
    device_index: int | None,
    callback: Callable[..., None],
    finished_callback: Callable[[], None] | None,
) -> sd.InputStream | sd.OutputStream:
    stream_class: Any = sd.InputStream if kind == "input" else sd.OutputStream
    try:
        device = sd.query_devices(device_index, kind)
        return stream_class(
            device=device_index,
            samplerate=device["default_samplerate"],
            channels=STREAM_CHANNELS,
            dtype=STREAM_DTYPE,
            callback=callback,
            finished_callback=finished_callback,
            extra_settings=_extra_settings(device),
        )
    except (sd.PortAudioError, ValueError) as error:
        device_label = "the default device" if device_index is None else f"device {device_index}"
        message = f"could not open {kind} stream on {device_label}: {error}"
        raise AudioStreamError(message) from error


def _extra_settings(device: dict[str, Any]) -> sd.WasapiSettings | None:
    hostapi_name = sd.query_hostapis(device["hostapi"])["name"]
    return sd.WasapiSettings(auto_convert=True) if hostapi_name == WASAPI_HOSTAPI else None
