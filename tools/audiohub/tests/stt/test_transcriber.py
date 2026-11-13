"""Tests for audiohub.stt.transcriber, using the fake WhisperModel from conftest.py.

The real model is exercised by hand with `audiohub listen`.
"""

import numpy as np
import pytest

from audiohub.config import SttSettings
from audiohub.stt import Transcriber
from audiohub.stt.transcriber import BEAM_SIZE, decode_options

ONE_SECOND = np.zeros(16_000, dtype=np.float32)


def test_nothing_is_loaded_until_needed(whisper_factory) -> None:
    transcriber = Transcriber(SttSettings(), whisper_factory)
    assert transcriber.device_in_use is None
    assert transcriber.model_in_use is None
    assert whisper_factory.built == []


def test_load_reports_the_device_and_model(whisper_factory) -> None:
    transcriber = Transcriber(SttSettings(), whisper_factory)
    transcriber.load()
    assert (transcriber.device_in_use, transcriber.model_in_use) == ("cuda", "large-v3-turbo")


def test_cpu_fallback_is_reported(whisper_factory) -> None:
    whisper_factory.fail_decode_on = {"cuda"}
    transcriber = Transcriber(SttSettings(), whisper_factory)
    transcriber.load()
    assert (transcriber.device_in_use, transcriber.model_in_use) == ("cpu", "small.en")


def test_model_is_loaded_once_across_calls(whisper_factory) -> None:
    transcriber = Transcriber(SttSettings(), whisper_factory)
    transcriber.load()
    transcriber.transcribe(ONE_SECOND)
    transcriber.transcribe(ONE_SECOND)
    assert len(whisper_factory.built) == 1


def test_segments_are_joined_and_trimmed(whisper_factory) -> None:
    whisper_factory.texts = [" Hey Claude,", " what's the weather like? "]
    text = Transcriber(SttSettings(), whisper_factory).transcribe(ONE_SECOND)
    assert text == "Hey Claude, what's the weather like?"


def test_hallucinations_are_filtered(whisper_factory) -> None:
    whisper_factory.texts = [" Thank you."]
    assert Transcriber(SttSettings(), whisper_factory).transcribe(ONE_SECOND) == ""


def test_decode_options_are_passed_to_whisper(whisper_factory) -> None:
    transcriber = Transcriber(SttSettings(language="en"), whisper_factory)
    transcriber.transcribe(ONE_SECOND.astype(np.float64))
    call = whisper_factory.built[0].calls[-1]
    assert call["dtype"] == np.float32
    assert call["language"] == "en"
    assert call["beam_size"] == BEAM_SIZE
    assert call["vad_filter"] is False
    assert call["condition_on_previous_text"] is False


def test_empty_language_means_autodetect() -> None:
    assert decode_options(SttSettings(language=""))["language"] is None


def test_empty_audio_returns_empty_without_loading(whisper_factory) -> None:
    transcriber = Transcriber(SttSettings(), whisper_factory)
    assert transcriber.transcribe(np.zeros(0, dtype=np.float32)) == ""
    assert whisper_factory.built == []


def test_multichannel_audio_is_rejected(whisper_factory) -> None:
    with pytest.raises(ValueError, match="mono"):
        Transcriber(SttSettings(), whisper_factory).transcribe(np.zeros((2, 16_000)))


def test_load_failure_propagates(whisper_factory) -> None:
    whisper_factory.fail_build_on = {"cuda", "cpu"}
    with pytest.raises(RuntimeError, match="no Whisper model"):
        Transcriber(SttSettings(), whisper_factory).transcribe(ONE_SECOND)
