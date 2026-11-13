"""The wake chime: a short two-tone "I'm listening" sound, and the task that plays it.

When the hub accepts a wake phrase ("Hey Claude" alone, or a request that
starts with one) the conversation calls `WakeChime.request()`. The chime runs
as its own loop, so hearing never waits for it, and it plays through
`VoiceOutput.play_cue`: the same speaker as Claude's voice (the glasses, or
the phone page with `run --phone`), with music ducked the same way.

It is deliberately not speech to the rest of the hub: it opens no speech
window, so what the user says right after it isn't "talking over Claude",
and it has no words for the echo check to match. Whisper rarely makes words
of a soft tone, and the hallucination filter drops the stock ones it does.
"""

import asyncio
import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

CHIME_SAMPLE_RATE = 24000
# Two soft rising tones, E5 then A5 (a fourth up), like an assistant's
# "listening" earcon. About 0.27 s in all.
CHIME_TONES_HZ = (659.25, 880.0)
CHIME_TONE_S = (0.11, 0.14)
CHIME_GAP_S = 0.02
# Envelope: a quick attack and an exponential, bell-like decay, with a short
# fade at the end so the tone never stops on a click.
ATTACK_S = 0.008
DECAY_S = 0.06
RELEASE_S = 0.015


class CuePlayer(Protocol):
    """What the chime needs from `VoiceOutput`."""

    async def play_cue(self, samples: np.ndarray, sample_rate: int) -> bool:
        """Play a short non-speech sound with music ducked."""
        ...


def make_chime(volume: float, sample_rate: int = CHIME_SAMPLE_RATE) -> np.ndarray:
    """Synthesize the wake chime.

    Args:
        volume: Peak level, 0.0 to 1.0.
        sample_rate: Samples per second of the result.

    Returns:
        Mono float32 samples in [-volume, volume].
    """
    first, second = (
        _tone(frequency, duration_s, sample_rate)
        for frequency, duration_s in zip(CHIME_TONES_HZ, CHIME_TONE_S, strict=True)
    )
    gap = np.zeros(round(CHIME_GAP_S * sample_rate))
    chime = np.concatenate([first, gap, second])
    # The envelope never quite reaches 1.0, so scale the real peak to `volume`.
    return (chime / np.abs(chime).max() * volume).astype(np.float32)


def _tone(frequency: float, duration_s: float, sample_rate: int) -> np.ndarray:
    """One enveloped sine tone, peaking a little under 1.0."""
    t = np.arange(round(duration_s * sample_rate)) / sample_rate
    attack = np.minimum(t / ATTACK_S, 1.0)
    release = np.clip((duration_s - t) / RELEASE_S, 0.0, 1.0)
    return np.sin(2 * np.pi * frequency * t) * attack * np.exp(-t / DECAY_S) * release


class WakeChime:
    """Plays the chime on request without blocking the caller. Run `run()` as a task."""

    def __init__(self, player: CuePlayer, volume: float) -> None:
        """Prepare the chime; nothing plays until `run()` is running.

        Args:
            player: The hub's voice output.
            volume: Peak level, 0.0 to 1.0 (`audio.wake_chime_volume`).
        """
        self._player = player
        self._samples = make_chime(volume)
        self._is_requested = asyncio.Event()

    def request(self) -> None:
        """Chime soon. Requests made before it plays are merged into one chime."""
        self._is_requested.set()

    async def run(self) -> None:
        """Play the chime each time it is requested, forever (until cancelled)."""
        while True:
            await self._is_requested.wait()
            self._is_requested.clear()
            try:
                await self._player.play_cue(self._samples, CHIME_SAMPLE_RATE)
            except Exception:
                # Broad on purpose: a missing output device costs the chime,
                # never the hub; speech reports the same failure on its own.
                logger.exception("could not play the wake chime")
