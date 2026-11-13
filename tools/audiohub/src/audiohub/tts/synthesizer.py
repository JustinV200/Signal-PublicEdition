"""Turn text into audio with the Kokoro ONNX model.

Last stage of the speech front end, after `clean_for_speech` and
`split_sentences`. Synthesis is synchronous and CPU-heavy, so the voice output
runs it in an executor. The model is loaded, and downloaded if missing, on the
first call rather than at construction. That keeps creating a Synthesizer
cheap and lets CLI commands that never speak start fast.
"""

import threading
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

from audiohub.config import TtsSettings
from audiohub.tts.models import ensure_models


class Synthesizer:
    """Synthesizes speech with Kokoro, using the voice, speed and language in settings."""

    def __init__(self, tts_settings: TtsSettings, models_dir: Path) -> None:
        """Remember the settings. Nothing is loaded until the first synthesis.

        Args:
            tts_settings: Default voice, speed and language (e.g. "en-gb").
            models_dir: Where the Kokoro model files live or will be downloaded.
        """
        self._settings = tts_settings
        self._models_dir = models_dir
        self._engine: Kokoro | None = None
        # Callers run synthesize in executor threads, so two first calls
        # could race to load the ~300 MB model twice.
        self._load_lock = threading.Lock()

    def synthesize(self, text: str, voice: str | None = None) -> tuple[np.ndarray, int]:
        """Speak `text` and return the audio.

        The first call loads the model, downloading it if needed, which can
        take a while.

        Args:
            text: Plain text to speak, ideally one sentence from `split_sentences`.
            voice: A Kokoro voice name, or None for the settings' voice.

        Returns:
            `(samples, sample_rate)`: mono float32 samples in [-1, 1] and their
            sample rate (24000 for Kokoro v1.0).

        Raises:
            ValueError: If `text` is blank, the voice isn't in the voices file,
                or the text produces no phonemes.
            ModelDownloadError: If the model files are missing and can't be
                downloaded.
        """
        if not text.strip():
            raise ValueError("Nothing to synthesize: the text is empty")
        engine = self._load_engine()
        # Concurrent calls are safe. kokoro_onnx serialises the espeak-ng
        # phonemizer (process-global state) behind its own lock, `create`
        # doesn't mutate the engine, and onnxruntime's InferenceSession.run
        # is thread-safe.
        samples, sample_rate = engine.create(
            text,
            voice=voice or self._settings.voice,
            speed=self._settings.speed,
            lang=self._settings.lang,
        )
        return np.asarray(samples, dtype=np.float32), sample_rate

    def _load_engine(self) -> Kokoro:
        """Return the Kokoro engine, loading it on first use."""
        with self._load_lock:
            if self._engine is None:
                model_path, voices_path = ensure_models(self._models_dir)
                self._engine = Kokoro(str(model_path), str(voices_path))
            return self._engine
