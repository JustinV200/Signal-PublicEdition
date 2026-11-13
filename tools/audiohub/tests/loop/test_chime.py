"""Tests for the wake chime: the sound it makes and the task that plays it."""

import asyncio

import numpy as np
import pytest

from audiohub.loop.chime import CHIME_SAMPLE_RATE, WakeChime, make_chime

VOLUME = 0.3


def test_chime_is_short_soft_and_starts_and_ends_silent():
    chime = make_chime(VOLUME)
    assert chime.dtype == np.float32
    assert 0.15 <= len(chime) / CHIME_SAMPLE_RATE <= 0.3
    assert np.abs(chime).max() == pytest.approx(VOLUME)
    # No click at either end.
    assert abs(chime[0]) < 0.01 and abs(chime[-1]) < 0.01


class FakeCuePlayer:
    def __init__(self, error: Exception | None = None) -> None:
        self.played: list[tuple[int, int]] = []
        self.error = error

    async def play_cue(self, samples: np.ndarray, sample_rate: int) -> bool:
        self.played.append((len(samples), sample_rate))
        if self.error is not None:
            raise self.error
        return True


@pytest.mark.asyncio
async def test_requests_before_it_plays_make_one_chime_and_a_failure_is_survived(fakes):
    player = FakeCuePlayer(error=OSError("output device gone"))
    chime = WakeChime(player, VOLUME)
    task = asyncio.create_task(chime.run())
    try:
        chime.request()
        chime.request()
        await fakes.wait_until(lambda: player.played)
        await asyncio.sleep(0.02)
        assert len(player.played) == 1
        chime.request()  # the failed play didn't stop the loop
        await fakes.wait_until(lambda: len(player.played) == 2)
    finally:
        task.cancel()
    assert player.played[0] == (len(make_chime(VOLUME)), CHIME_SAMPLE_RATE)
