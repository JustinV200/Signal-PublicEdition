"""Tests for audiohub.music.fallback: when FallbackController drops to the fallback backend."""

import pytest

from audiohub.music import (
    FALLBACK_REASONS,
    FallbackController,
    MusicUnavailable,
    NowPlaying,
    UnavailableReason,
)

TRANSPORT_METHODS = ["play", "pause", "toggle", "next", "previous", "now_playing"]


def unavailable(reason: UnavailableReason) -> MusicUnavailable:
    return MusicUnavailable(f"because {reason}", reason)


@pytest.fixture
def pair(make_controller):
    primary, fallback = make_controller("spotify"), make_controller("smtc")
    return primary, fallback, FallbackController(primary, fallback)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", TRANSPORT_METHODS)
async def test_transport_uses_primary_when_it_works(pair, method):
    primary, fallback, controller = pair
    await getattr(controller, method)()
    assert primary.calls == [(method,)]
    assert fallback.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method", TRANSPORT_METHODS)
async def test_transport_falls_back_when_primary_is_unusable(pair, method):
    primary, fallback, controller = pair
    primary.failures[method] = unavailable(UnavailableReason.NOT_CONFIGURED)
    await getattr(controller, method)()
    assert fallback.calls == [(method,)]


@pytest.mark.parametrize(
    "reason",
    [
        UnavailableReason.RATE_LIMITED,
        UnavailableReason.NOT_FOUND,
    ],
)
@pytest.mark.asyncio
async def test_refusals_are_reported_not_hidden_by_the_fallback(pair, reason):
    primary, fallback, controller = pair
    primary.failures["pause"] = unavailable(reason)
    with pytest.raises(MusicUnavailable) as error:
        await controller.pause()
    assert error.value.reason is reason
    assert fallback.calls == []


@pytest.mark.asyncio
async def test_fallback_errors_propagate(pair):
    primary, fallback, controller = pair
    primary.failures["play"] = unavailable(UnavailableReason.NOT_CONFIGURED)
    fallback.failures["play"] = unavailable(UnavailableReason.NO_SESSION)
    with pytest.raises(MusicUnavailable) as error:
        await controller.play()
    assert error.value.reason is UnavailableReason.NO_SESSION


@pytest.mark.asyncio
async def test_now_playing_comes_from_the_fallback_when_needed(pair):
    primary, fallback, controller = pair
    primary.failures["now_playing"] = unavailable(UnavailableReason.NO_ACTIVE_DEVICE)
    fallback.playing = NowPlaying("Babydoll", "Dominic Fike", "", True, "smtc:Spotify.exe")
    assert await controller.now_playing() == fallback.playing


@pytest.mark.asyncio
async def test_volume_search_and_queue_only_use_the_primary(pair):
    primary, fallback, controller = pair
    await controller.set_volume(40)
    assert await controller.search_and_play("jazz", "playlist") == "spotify played jazz"
    assert await controller.queue("babydoll") == "spotify queued babydoll"
    assert primary.calls == [
        ("set_volume", 40),
        ("search_and_play", "jazz", "playlist"),
        ("queue", "babydoll"),
    ]
    assert fallback.calls == []


@pytest.mark.asyncio
async def test_volume_search_and_queue_report_the_premium_message(pair):
    primary, fallback, controller = pair
    premium = unavailable(UnavailableReason.PREMIUM_REQUIRED)
    for method in ("set_volume", "search_and_play", "queue"):
        primary.failures[method] = premium
    with pytest.raises(MusicUnavailable) as volume_error:
        await controller.set_volume(30)
    with pytest.raises(MusicUnavailable) as search_error:
        await controller.search_and_play("jazz")
    with pytest.raises(MusicUnavailable) as queue_error:
        await controller.queue("jazz")
    assert volume_error.value is search_error.value is queue_error.value is premium
    assert fallback.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", sorted(FALLBACK_REASONS))
async def test_pause_and_now_playing_use_the_same_backend(pair, reason):
    # Whenever the primary is unusable for pause it is for now_playing too, so
    # the two never disagree by talking to different backends.
    primary, fallback, controller = pair
    primary.failures["pause"] = unavailable(reason)
    primary.failures["now_playing"] = unavailable(reason)
    await controller.pause()
    await controller.now_playing()
    assert [c[0] for c in fallback.calls] == ["pause", "now_playing"]


@pytest.mark.asyncio
async def test_premium_required_pause_is_reported_not_sent_to_the_fallback(pair):
    primary, fallback, controller = pair
    primary.failures["pause"] = unavailable(UnavailableReason.PREMIUM_REQUIRED)
    with pytest.raises(MusicUnavailable):
        await controller.pause()
    assert fallback.calls == []
