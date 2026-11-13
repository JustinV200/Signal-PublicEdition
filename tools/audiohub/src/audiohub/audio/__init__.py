"""Public API of audiohub.audio: devices, microphone, speaker, resampling, ducking.

Other packages import audio features from here only.
"""

from audiohub.audio.device_names import BLUETOOTH, HANDS_FREE, bluetooth_hints
from audiohub.audio.devices import (
    PREFERRED_HOSTAPIS,
    DeviceInfo,
    DeviceKind,
    DeviceNotFoundError,
    list_devices,
    resolve_device,
)
from audiohub.audio.ducking import Ducker, list_session_process_names
from audiohub.audio.framing import FrameChunker
from audiohub.audio.microphone import Microphone
from audiohub.audio.resample import StreamResampler, resample
from audiohub.audio.speaker import Speaker
from audiohub.audio.streams import AudioStreamError

__all__ = [
    "BLUETOOTH",
    "HANDS_FREE",
    "PREFERRED_HOSTAPIS",
    "AudioStreamError",
    "DeviceInfo",
    "DeviceKind",
    "DeviceNotFoundError",
    "Ducker",
    "FrameChunker",
    "Microphone",
    "Speaker",
    "StreamResampler",
    "bluetooth_hints",
    "list_devices",
    "list_session_process_names",
    "resample",
    "resolve_device",
]
