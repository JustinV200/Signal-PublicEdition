"""Public API of audiohub.tts: text cleaning, sentence chunking and Kokoro speech.

The voice output runs clean_for_speech -> split_sentences -> Synthesizer for
each message. Other packages import from here only. tts depends on
audiohub.config and never on audiohub.audio.
"""

from audiohub.tts.cleaning import clean_for_speech
from audiohub.tts.download import ModelDownloadError
from audiohub.tts.models import ensure_models
from audiohub.tts.sentences import split_sentences
from audiohub.tts.synthesizer import Synthesizer
from audiohub.tts.voices import BRITISH_MALE_VOICES

__all__ = [
    "BRITISH_MALE_VOICES",
    "ModelDownloadError",
    "Synthesizer",
    "clean_for_speech",
    "ensure_models",
    "split_sentences",
]
