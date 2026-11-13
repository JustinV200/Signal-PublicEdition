"""Tests for audiohub.tts.synthesizer: lazy loading and settings pass-through.

Kokoro and ensure_models are replaced with fakes, so these run without the
model files. The real model is exercised by hand with `audiohub say`.
"""

import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from audiohub.config import TtsSettings
from audiohub.tts import Synthesizer

FAKE_SAMPLE_RATE = 24000


class FakeKokoro:
    """Stands in for kokoro_onnx.Kokoro and records how it is used."""

    instances: list["FakeKokoro"] = []

    def __init__(self, model_path: str, voices_path: str) -> None:
        # Widen the window in which two threads could both start a load.
        time.sleep(0.05)
        self.paths = (model_path, voices_path)
        self.calls: list[dict[str, Any]] = []
        FakeKokoro.instances.append(self)

    def create(self, text: str, **options: Any) -> tuple[np.ndarray, int]:
        self.calls.append({"text": text, **options})
        # float64, to check the synthesizer hands back float32.
        return np.full(480, 0.5, dtype=np.float64), FAKE_SAMPLE_RATE


@pytest.fixture
def ensured_dirs(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Install the fakes and return the folders ensure_models was asked for."""
    FakeKokoro.instances = []
    ensured: list[Path] = []

    def fake_ensure_models(models_dir: Path) -> tuple[Path, Path]:
        ensured.append(models_dir)
        return models_dir / "model.onnx", models_dir / "voices.bin"

    monkeypatch.setattr("audiohub.tts.synthesizer.Kokoro", FakeKokoro)
    monkeypatch.setattr("audiohub.tts.synthesizer.ensure_models", fake_ensure_models)
    return ensured


def test_construction_loads_nothing(ensured_dirs: list[Path], tmp_path: Path) -> None:
    Synthesizer(TtsSettings(), tmp_path)

    assert ensured_dirs == []
    assert FakeKokoro.instances == []


def test_first_synthesis_loads_the_model_once(ensured_dirs: list[Path], tmp_path: Path) -> None:
    synthesizer = Synthesizer(TtsSettings(), tmp_path)

    synthesizer.synthesize("One.")
    synthesizer.synthesize("Two.")

    assert ensured_dirs == [tmp_path]
    assert len(FakeKokoro.instances) == 1
    assert FakeKokoro.instances[0].paths == (
        str(tmp_path / "model.onnx"),
        str(tmp_path / "voices.bin"),
    )


def test_uses_voice_speed_and_language_from_settings(
    ensured_dirs: list[Path], tmp_path: Path
) -> None:
    settings = TtsSettings(voice="bm_lewis", speed=1.25, lang="en-gb")

    Synthesizer(settings, tmp_path).synthesize("Hello there.")

    assert FakeKokoro.instances[0].calls == [
        {"text": "Hello there.", "voice": "bm_lewis", "speed": 1.25, "lang": "en-gb"}
    ]


def test_voice_argument_overrides_the_settings_voice(
    ensured_dirs: list[Path], tmp_path: Path
) -> None:
    Synthesizer(TtsSettings(voice="bm_george"), tmp_path).synthesize("Hi.", voice="bm_fable")

    assert FakeKokoro.instances[0].calls[0]["voice"] == "bm_fable"


def test_returns_float32_samples_and_the_sample_rate(
    ensured_dirs: list[Path], tmp_path: Path
) -> None:
    samples, sample_rate = Synthesizer(TtsSettings(), tmp_path).synthesize("Hi.")

    assert samples.dtype == np.float32
    assert samples.shape == (480,)
    assert sample_rate == FAKE_SAMPLE_RATE


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_text_is_rejected_without_loading(
    ensured_dirs: list[Path], tmp_path: Path, text: str
) -> None:
    with pytest.raises(ValueError, match="empty"):
        Synthesizer(TtsSettings(), tmp_path).synthesize(text)

    assert FakeKokoro.instances == []


def test_concurrent_first_calls_load_the_model_once(
    ensured_dirs: list[Path], tmp_path: Path
) -> None:
    synthesizer = Synthesizer(TtsSettings(), tmp_path)
    start = threading.Barrier(4)

    def speak() -> None:
        start.wait()
        synthesizer.synthesize("Hi.")

    threads = [threading.Thread(target=speak) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(FakeKokoro.instances) == 1
    assert len(FakeKokoro.instances[0].calls) == 4
