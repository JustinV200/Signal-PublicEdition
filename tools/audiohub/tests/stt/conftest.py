"""Shared fakes for the audiohub.stt model-loader and transcriber tests.

pytest runs in importlib mode, so test modules can't import each other.
Shared helpers are exposed as fixtures instead:
- `whisper_factory` is a fake `WhisperModel` constructor. It records every
  model built and every transcribe call, and can be told to fail per device.
- An autouse fixture stops unit tests from changing the real PATH or DLL
  search directories.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

CUBLAS_MISSING = "Library cublas64_12.dll is not found or cannot be loaded"


@dataclass
class FakeWhisperModel:
    """Stands in for faster_whisper.WhisperModel."""

    name: str
    device: str
    compute_type: str
    texts: list[str]
    decode_error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def transcribe(self, audio: np.ndarray, **options: Any) -> tuple[Any, Any]:
        self.calls.append({"samples": len(audio), "dtype": audio.dtype, **options})
        if self.decode_error is not None:
            raise self.decode_error
        return iter(SimpleNamespace(text=text) for text in self.texts), None


@dataclass
class FakeWhisperFactory:
    """Callable like WhisperModel(name, device=..., compute_type=...)."""

    texts: list[str] = field(default_factory=lambda: [" Hello there."])
    # Devices whose construction raises, and devices whose decodes raise
    # (the latter mimics a CUDA model that builds but lacks cuBLAS).
    fail_build_on: set[str] = field(default_factory=set)
    fail_decode_on: set[str] = field(default_factory=set)
    built: list[FakeWhisperModel] = field(default_factory=list)

    def __call__(self, name: str, *, device: str, compute_type: str) -> FakeWhisperModel:
        if device in self.fail_build_on:
            raise RuntimeError(f"CUDA failed with error on {device}")
        decode_error = RuntimeError(CUBLAS_MISSING) if device in self.fail_decode_on else None
        model = FakeWhisperModel(name, device, compute_type, self.texts, decode_error)
        self.built.append(model)
        return model


@pytest.fixture
def whisper_factory() -> FakeWhisperFactory:
    return FakeWhisperFactory()


@pytest.fixture(autouse=True)
def _no_real_dll_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audiohub.stt.model_loader.register_nvidia_dll_dirs", lambda: [])
