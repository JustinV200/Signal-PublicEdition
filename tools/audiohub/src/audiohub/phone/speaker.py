"""`RemoteSpeaker`: plays the hub's speech on the phone, for VoiceOutput.

It stands where `audiohub.audio.Speaker` stands in `audiohub run`, with the
same `play` / `stop` contract: `play` returns once the phone reports the
chunk played, so VoiceOutput's pacing, the half-duplex mic pause and the echo
tail work as they do locally. The page acks a little before each chunk ends
(page/app.js ACK_LEAD_S), so the next sentence is queued behind it without a
gap; the echo tail after the last chunk covers that lead.
"""

import asyncio

import numpy as np

from audiohub.audio import AudioStreamError

from .link import PhoneLink

# Extra time beyond a chunk's duration before playback counts as stalled.
# Covers the network round trip, the page's audio start-up and a phone that
# was briefly busy; past it the phone is probably gone without a close.
ACK_DEADLINE_MARGIN_S = 5.0


class RemoteSpeaker:
    """Plays mono buffers on the phone, one at a time. Call from the event loop thread."""

    def __init__(self, link: PhoneLink) -> None:
        """Play through `link`, the phone connection the page is on."""
        self._link = link
        self._current: asyncio.Future[None] | None = None

    @property
    def is_playing(self) -> bool:
        """Whether a `play` call is in progress."""
        return self._current is not None

    async def play(self, samples: np.ndarray, sample_rate: int) -> None:
        """Send a mono buffer to the phone and return when it has played (or `stop()` was called).

        Args:
            samples: Mono float audio, shape `(n,)`, in [-1, 1].
            sample_rate: The buffer's rate in Hz; the page plays it at that rate.

        Raises:
            RuntimeError: If another `play` is already in progress.
            ValueError: If `sample_rate` is not positive.
            AudioStreamError: If no phone is connected, it disconnects first, or
                it doesn't ack within the buffer's duration plus
                ACK_DEADLINE_MARGIN_S.
        """
        if self._current is not None:
            raise RuntimeError("RemoteSpeaker is already playing; call stop() first")
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        if len(samples) == 0:
            return
        played = await self._link.send_speech(samples, sample_rate)
        self._current = played
        duration_s = len(samples) / sample_rate
        try:
            await asyncio.wait_for(played, duration_s + ACK_DEADLINE_MARGIN_S)
        except TimeoutError as error:
            raise AudioStreamError(
                f"the phone did not finish {duration_s:.1f}s of speech within "
                f"{duration_s + ACK_DEADLINE_MARGIN_S:.1f}s; it may have gone to sleep"
            ) from error
        finally:
            self._current = None

    def stop(self) -> None:
        """Cut playback short on the phone so `play` returns now. No-op when idle."""
        if self._current is None:
            return
        self._link.stop_speech()
        if not self._current.done():
            self._current.set_result(None)
