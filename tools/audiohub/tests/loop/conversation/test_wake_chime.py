"""End-to-end tests for the wake chime: it plays when a wake phrase is accepted, and only then."""

import asyncio
import time

import pytest

from audiohub.loop.chime import make_chime

CHIME_SAMPLES = len(make_chime(0.3))


@pytest.mark.asyncio
async def test_a_bare_wake_phrase_chimes_and_the_request_after_it_is_asked(fakes, make_hub):
    # Barge-in on: the chime opens no speech window, so the request said right
    # after it isn't "talking over Claude" and needs no wake phrase.
    hub = make_hub(barge_in=True, wake_chime=True)
    async with hub:
        hub.hearing.hear("Hey Claude.")
        # Chimed and done: speech queued during the chime would share its duck.
        await fakes.wait_until(lambda: hub.speaker.played and not hub.ducker.is_ducked)
        assert hub.speaker.played == [CHIME_SAMPLES]
        hub.hearing.hear("what's the time?")
        await fakes.wait_until(lambda: len(hub.speaker.played) == 2)
    assert hub.brain.requests == ["what's the time?"]
    assert hub.ducker.calls == ["duck", "restore"] * 2  # the chime ducks the music too


@pytest.mark.asyncio
async def test_a_wake_request_chimes_but_a_follow_up_does_not(fakes, make_hub):
    hub = make_hub(wake_chime=True)
    async with hub:
        hub.hearing.hear("Claude, what's the time?")
        # The chime and the reply have both played, and the reply's echo tail is over.
        await fakes.wait_until(lambda: len(hub.speaker.played) == 2 and not hub.ducker.is_ducked)
        await asyncio.sleep(0.1)
        hub.hearing.hear("And the date?", started_at=time.monotonic())  # a follow-up
        await fakes.wait_until(lambda: len(hub.brain.requests) == 2)
        await fakes.wait_until(lambda: len(hub.speaker.played) == 3)
    assert hub.speaker.played == [
        CHIME_SAMPLES,
        len("You said: what's the time?"),
        len("You said: And the date?"),
    ]
