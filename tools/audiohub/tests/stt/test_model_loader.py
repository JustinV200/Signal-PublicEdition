"""Tests for audiohub.stt.model_loader: model choices, warm-up and CPU fallback.

Uses the fake WhisperModel factory from conftest.py; no real model is loaded.
"""

import logging

import pytest

from audiohub.config import SttSettings
from audiohub.stt import model_loader
from audiohub.stt.model_loader import (
    WARMUP_SAMPLES,
    ModelChoice,
    load_whisper_model,
    model_choices,
)

OPTIONS = {"language": "en", "beam_size": 1, "vad_filter": False}
PRIMARY = ModelChoice("large-v3-turbo", "cuda", "float16")
FALLBACK = ModelChoice("small.en", "cpu", "int8")


def test_default_choices_are_gpu_then_cpu_fallback() -> None:
    assert model_choices(SttSettings()) == [PRIMARY, FALLBACK]


def test_fallback_is_skipped_when_it_equals_the_primary() -> None:
    settings = SttSettings(model="small.en", device="cpu", compute_type="int8")
    assert model_choices(settings) == [FALLBACK]


def test_primary_choice_is_used_when_it_works(whisper_factory) -> None:
    loaded = load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    assert loaded.choice == PRIMARY
    assert [model.device for model in whisper_factory.built] == ["cuda"]


def test_warm_up_decodes_silence_with_the_given_options(whisper_factory) -> None:
    loaded = load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    (warm_up,) = loaded.model.calls
    assert warm_up["samples"] == WARMUP_SAMPLES
    assert {key: warm_up[key] for key in OPTIONS} == OPTIONS


def test_falls_back_to_cpu_when_cuda_build_fails(
    whisper_factory, caplog: pytest.LogCaptureFixture
) -> None:
    whisper_factory.fail_build_on = {"cuda"}
    with caplog.at_level(logging.WARNING, logger=model_loader.__name__):
        loaded = load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    assert loaded.choice == FALLBACK
    assert "large-v3-turbo on cuda/float16 failed" in caplog.text


def test_falls_back_when_cuda_builds_but_first_decode_fails(whisper_factory) -> None:
    # The real Windows failure: the model builds, then cuBLAS fails to load.
    whisper_factory.fail_decode_on = {"cuda"}
    loaded = load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    assert loaded.choice == FALLBACK
    assert [model.device for model in whisper_factory.built] == ["cuda", "cpu"]


def test_raises_with_cause_when_every_choice_fails(whisper_factory) -> None:
    whisper_factory.fail_build_on = {"cuda", "cpu"}
    with pytest.raises(RuntimeError, match="no Whisper model") as raised:
        load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    assert "cpu" in str(raised.value.__cause__)


def test_dlls_are_registered_only_for_gpu_choices(
    whisper_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    registrations: list[bool] = []
    monkeypatch.setattr(
        model_loader, "register_nvidia_dll_dirs", lambda: registrations.append(True)
    )
    whisper_factory.fail_build_on = {"cuda"}
    load_whisper_model(SttSettings(), OPTIONS, whisper_factory)
    assert registrations == [True]
