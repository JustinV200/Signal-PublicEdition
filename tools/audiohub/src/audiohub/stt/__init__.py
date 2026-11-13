"""Public API of audiohub.stt: microphone frames in, utterance transcripts out.

Typical use, one frame at a time from `audiohub.audio.Microphone`:

    vad = VoiceActivityDetector(settings.vad.threshold)
    segmenter = UtteranceSegmenter(vad, settings.vad)
    transcriber = Transcriber(settings.stt)
    utterance = segmenter.push(frame)
    if utterance is not None:
        text = await loop.run_in_executor(None, transcriber.transcribe, utterance)

Other packages import from here only. This package depends on audiohub.config
and never on audiohub.audio.
"""

from audiohub.stt.frames import FRAME_SAMPLES, SAMPLE_RATE
from audiohub.stt.segmenter import SpeechScorer, UtteranceSegmenter
from audiohub.stt.transcriber import Transcriber
from audiohub.stt.vad import VoiceActivityDetector

__all__ = [
    "FRAME_SAMPLES",
    "SAMPLE_RATE",
    "SpeechScorer",
    "Transcriber",
    "UtteranceSegmenter",
    "VoiceActivityDetector",
]
