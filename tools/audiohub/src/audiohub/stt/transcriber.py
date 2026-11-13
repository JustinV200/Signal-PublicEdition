"""Speech-to-text for one segmented utterance with faster-whisper.

The segmenter has already cut the audio to a single utterance, so Whisper's
own VAD is off. Each call is independent: no text carries over from earlier
utterances. The model loads lazily on first use, or eagerly via `load()`.
Loading tries CUDA first and falls back to CPU (see model_loader.py). The
output goes through the hallucination filter.
"""

import logging
import threading
from typing import Any

import numpy as np

from audiohub.config import SttSettings
from audiohub.stt.hallucinations import remove_hallucinations
from audiohub.stt.model_loader import LoadedModel, ModelFactory, load_whisper_model

logger = logging.getLogger(__name__)

# Decode tunables stay in code, not config: the brief fixes the [stt] schema,
# and these were picked from latency measurements, not per-machine taste.

# Beam search width. Measured on a 3.5 s utterance, beam 5 vs greedy:
# desktop GPU large-v3-turbo 72 vs 67 ms, CPU small.en int8 903 vs 894 ms.
# The encoder dominates, so the wider beam (more robust on noisy narrowband
# audio) costs almost no latency. It does grow with very long utterances.
BEAM_SIZE = 5

# Retry at a higher temperature only once when a decode looks degenerate
# (repetition, low confidence). faster-whisper's default ladder of six steps
# can multiply latency on noisy audio.
TEMPERATURES = (0.0, 0.4)


def decode_options(stt_settings: SttSettings) -> dict[str, Any]:
    """Build the `WhisperModel.transcribe` keyword arguments audiohub uses.

    Args:
        stt_settings: Supplies `language`; "" means let Whisper detect it.

    Returns:
        A fresh dict of decode options.
    """
    return {
        "language": stt_settings.language or None,
        "beam_size": BEAM_SIZE,
        "temperature": list(TEMPERATURES),
        "vad_filter": False,
        "condition_on_previous_text": False,
        "without_timestamps": True,
    }


class Transcriber:
    """Turns an utterance into text. Synchronous: run it in an executor."""

    def __init__(
        self, stt_settings: SttSettings, model_factory: ModelFactory | None = None
    ) -> None:
        """Prepare a transcriber. No model is loaded yet.

        Args:
            stt_settings: Model, device, precision, fallback model and language.
            model_factory: Builds a model; defaults to `faster_whisper.WhisperModel`.
                Tests pass a fake.
        """
        self._settings = stt_settings
        self._model_factory = model_factory
        self._options = decode_options(stt_settings)
        self._loaded: LoadedModel | None = None
        # Loading can be triggered from several executor threads at once.
        self._load_lock = threading.Lock()

    @property
    def device_in_use(self) -> str | None:
        """ "cuda" or "cpu" once a model is loaded, otherwise None."""
        return self._loaded.choice.device if self._loaded else None

    @property
    def model_in_use(self) -> str | None:
        """Name of the loaded model (it differs after a fallback), otherwise None."""
        return self._loaded.choice.model if self._loaded else None

    def load(self) -> None:
        """Load and warm up the model now, if it isn't loaded yet.

        Raises:
            RuntimeError: If neither the configured nor the fallback model loads.
        """
        self._ensure_loaded()

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe one utterance.

        Args:
            audio: float32 mono 16 kHz samples, e.g. from `UtteranceSegmenter.push`.

        Returns:
            The transcript, stripped of known Whisper hallucinations. Empty if
            nothing real was said.

        Raises:
            ValueError: If `audio` is not a 1-D array.
            RuntimeError: If no model could be loaded.
        """
        samples = np.ascontiguousarray(audio, dtype=np.float32)
        if samples.ndim != 1:
            raise ValueError(f"expected mono 1-D audio, got shape {samples.shape}")
        if samples.size == 0:
            return ""
        segments, _info = self._ensure_loaded().model.transcribe(samples, **self._options)
        raw_text = " ".join(segment.text.strip() for segment in segments)
        cleaned = remove_hallucinations(raw_text)
        if cleaned != raw_text.strip():
            logger.debug("hallucination filter: %r -> %r", raw_text, cleaned)
        return cleaned

    def _ensure_loaded(self) -> LoadedModel:
        with self._load_lock:
            if self._loaded is None:
                self._loaded = load_whisper_model(
                    self._settings, self._options, self._model_factory
                )
            return self._loaded
