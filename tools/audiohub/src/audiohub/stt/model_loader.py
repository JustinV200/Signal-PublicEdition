"""Loads a faster-whisper model, falling back from the GPU to the CPU.

The first choice comes from SttSettings (default large-v3-turbo, CUDA,
float16). If it can't be loaded, the loader logs why and tries
`fallback_model` on CPU with int8. Each candidate is warmed up with a short
silent decode. On Windows, building a CUDA model succeeds even when
cuBLAS/cuDNN are missing. The failure only shows on the first decode, so the
warm-up is what makes the fallback reliable. Models download into the Hugging
Face cache on first use.
"""

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from audiohub.config import SttSettings
from audiohub.stt.cuda_dlls import register_nvidia_dll_dirs
from audiohub.stt.frames import SAMPLE_RATE

logger = logging.getLogger(__name__)

FALLBACK_DEVICE = "cpu"
FALLBACK_COMPUTE_TYPE = "int8"

# Half a second of silence is enough to run the encoder and one decode step.
WARMUP_SAMPLES = SAMPLE_RATE // 2


class WhisperSegment(Protocol):
    """The part of faster_whisper's `Segment` that audiohub reads."""

    text: str


class WhisperLike(Protocol):
    """The part of `faster_whisper.WhisperModel` that audiohub calls."""

    def transcribe(self, audio: np.ndarray, **options: Any) -> tuple[Iterable[WhisperSegment], Any]:
        """Transcribe 16 kHz float32 audio; segments are produced lazily."""
        ...


# Builds a model from (model name, device=..., compute_type=...).
ModelFactory = Callable[..., WhisperLike]


@dataclass(frozen=True)
class ModelChoice:
    """One model/device/precision combination to try."""

    model: str
    device: str
    compute_type: str


@dataclass(frozen=True)
class LoadedModel:
    """A model that passed its warm-up decode, and the choice that produced it."""

    model: WhisperLike
    choice: ModelChoice


def model_choices(stt_settings: SttSettings) -> list[ModelChoice]:
    """List the combinations to try, in order: configured first, then CPU fallback.

    Args:
        stt_settings: Model, device, compute type and fallback model.

    Returns:
        One or two choices. The fallback is left out when it equals the primary.
    """
    primary = ModelChoice(stt_settings.model, stt_settings.device, stt_settings.compute_type)
    fallback = ModelChoice(stt_settings.fallback_model, FALLBACK_DEVICE, FALLBACK_COMPUTE_TYPE)
    return [primary] if fallback == primary else [primary, fallback]


def load_whisper_model(
    stt_settings: SttSettings,
    decode_options: dict[str, Any],
    factory: ModelFactory | None = None,
) -> LoadedModel:
    """Load and warm up the first model choice that works.

    Args:
        stt_settings: Which models to try.
        decode_options: Keyword arguments for `transcribe`, the same ones real
            transcription uses, so the warm-up runs the same decode path.
        factory: Builds a model. Defaults to `faster_whisper.WhisperModel`.

    Returns:
        The loaded model and the choice that worked.

    Raises:
        RuntimeError: If every choice failed. The last failure is chained.
    """
    last_error: Exception | None = None
    for choice in model_choices(stt_settings):
        try:
            return _load_choice(choice, decode_options, factory)
        # Broad on purpose: CUDA, cuDNN, download and model-format failures
        # all surface as different exception types, and each should fall back.
        except Exception as error:
            logger.warning(
                "STT model %s on %s/%s failed: %s",
                choice.model,
                choice.device,
                choice.compute_type,
                error,
            )
            last_error = error
    raise RuntimeError("no Whisper model could be loaded; see the warnings above") from last_error


def _load_choice(
    choice: ModelChoice, decode_options: dict[str, Any], factory: ModelFactory | None
) -> LoadedModel:
    started = time.perf_counter()
    if choice.device != FALLBACK_DEVICE:
        register_nvidia_dll_dirs()
    build = factory or _default_factory()
    model = build(choice.model, device=choice.device, compute_type=choice.compute_type)
    segments, _info = model.transcribe(np.zeros(WARMUP_SAMPLES, dtype=np.float32), **decode_options)
    # Segments are lazy: consuming them is what actually runs the GPU kernels.
    list(segments)
    logger.info(
        "STT model %s loaded on %s/%s in %.1f s",
        choice.model,
        choice.device,
        choice.compute_type,
        time.perf_counter() - started,
    )
    return LoadedModel(model=model, choice=choice)


def _default_factory() -> ModelFactory:
    # Imported here, after the DLL setup, and only when a model is needed:
    # faster_whisper pulls in CTranslate2, PyAV and tokenizers (~1 s to import).
    from faster_whisper import WhisperModel

    return WhisperModel
