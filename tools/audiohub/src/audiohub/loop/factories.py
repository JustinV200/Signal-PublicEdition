"""Build the loop's audio components from settings: the voice output and the hearing pipeline.

Shared by the conversation and by the `say`, `voices` and `listen` commands,
so every entry point wires the devices, models and ducking the same way.
"""

from audiohub.audio import Ducker, Microphone, Speaker
from audiohub.config import MODELS_DIR, Settings
from audiohub.stt import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    Transcriber,
    UtteranceSegmenter,
    VoiceActivityDetector,
)
from audiohub.tts import Synthesizer

from .hearing import FrameSource, Hearing
from .voice_output import AudioPlayer, VoiceOutput


def create_voice_output(settings: Settings, speaker: AudioPlayer | None = None) -> VoiceOutput:
    """Kokoro TTS on the configured output device, with music ducking.

    Nothing opens here: the TTS model loads (downloading if missing) on first
    use, and the output device is looked up each time a chunk plays.

    Args:
        settings: Supplies the output device, voice and ducking settings.
        speaker: Plays the speech instead of the configured output device,
            e.g. the phone bridge's RemoteSpeaker.
    """
    return VoiceOutput(
        Synthesizer(settings.tts, MODELS_DIR),
        speaker or Speaker(settings.audio.output_device),
        Ducker(settings.ducking),
    )


def create_hearing(settings: Settings, source: FrameSource | None = None) -> Hearing:
    """VAD segmentation and Whisper over a frame source (the configured mic by default).

    Args:
        settings: Supplies the input device and the VAD and STT settings.
        source: A stand-in such as WavFrameSource; None uses the microphone,
            which looks up `audio.input_device` when the Hearing is entered.
    """
    if source is None:
        source = Microphone(settings.audio.input_device, FRAME_SAMPLES, SAMPLE_RATE)
    segmenter = UtteranceSegmenter(VoiceActivityDetector(settings.vad.threshold), settings.vad)
    return Hearing(source, segmenter, Transcriber(settings.stt))
