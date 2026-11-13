"""End-to-end tests of the music pause in a whole hub: its wake and speech hook points.

The music pause's own rules (grace period, what is left alone) are tested in
tests/loop/test_music_pause.py; here the test hub resumes with no grace.
"""

import pytest

from audiohub.kernel import create_message


@pytest.mark.asyncio
async def test_a_notification_pauses_the_music_only_while_it_is_spoken(fakes, make_hub):
    music = fakes.Music()
    hub = make_hub(listen=False, music=music)
    hub.speaker.play_s = 0.3  # long enough for the music pause's poll to see the speech
    async with hub:
        hub.parts.kernel.submit(create_message("build", "The build finished.", "normal"))
        await fakes.wait_until(lambda: "play" in music.names)
    assert music.names == ["now_playing", "pause", "now_playing", "play"]
    speech_ended_at = hub.speaker.play_spans[-1][1]
    assert music.time_of("pause") < speech_ended_at < music.time_of("play")


@pytest.mark.asyncio
async def test_a_hung_music_backend_never_holds_up_the_replies(fakes, make_hub):
    music = fakes.Music()
    music.hangs.add("now_playing")
    hub = make_hub(music=music)
    async with hub:
        hub.hearing.hear("Hey Claude, what's the time?")
        # The wake reached the music pause, whose first call now never returns.
        await fakes.wait_until(lambda: music.names == ["now_playing"])
        hub.hearing.hear("Hey Claude, and the date?")
        await fakes.wait_until(lambda: len(hub.speaker.played) == 2)
    assert hub.brain.requests == ["what's the time?", "and the date?"]
