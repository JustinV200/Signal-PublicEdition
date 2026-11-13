"""Public API of audiohub.loop.hearing: audio frames in, transcripts out.

`Hearing` runs the STT front end over any `FrameSource`: the real
`audiohub.audio.Microphone`, or `WavFrameSource` for tests and hands-off runs.
"""

from .frame_source import FrameSource
from .hearing import Heard, Hearing
from .wav_source import WavFrameSource, read_wav_mono

__all__ = ["FrameSource", "Heard", "Hearing", "WavFrameSource", "read_wav_mono"]
