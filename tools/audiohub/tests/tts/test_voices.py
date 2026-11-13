"""Tests for audiohub.tts.voices: the British male voice list is real.

The check against voices-v1.0.bin only runs once the model files have been
downloaded (by `audiohub say` or any first synthesis). Without them it skips.
"""

import numpy as np
import pytest

from audiohub.config import MODELS_DIR
from audiohub.tts import BRITISH_MALE_VOICES
from audiohub.tts.models import VOICES_FILENAME

VOICES_PATH = MODELS_DIR / VOICES_FILENAME


@pytest.mark.skipif(not VOICES_PATH.is_file(), reason="Kokoro voices file not downloaded")
def test_every_voice_exists_in_the_voices_file() -> None:
    with np.load(VOICES_PATH) as voices:
        available = set(voices.files)

    assert set(BRITISH_MALE_VOICES) <= available
