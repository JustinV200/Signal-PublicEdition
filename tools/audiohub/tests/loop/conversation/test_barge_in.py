"""End-to-end barge-in tests: cutting in over Claude by voice, with the mic left live.

Built on the `make_hub` fixture (real kernel and voice output, fake brain,
hearing, TTS and speaker). The fake speaker "plays" for `play_s`, so a long
`play_s` keeps Claude talking while the test speaks over it.
"""

import asyncio
import logging
import time

import pytest

from audiohub.brain import ReplyText
from audiohub.kernel import create_message

LONG_PLAY_S = 10.0
SHORT_PLAY_S = 0.01
# How long the fake brain takes to answer a new request. Real answers take
# seconds; replies within one clock tick of a cut count as stale.
ANSWER_DELAY_S = 0.05


@pytest.mark.asyncio
async def test_stop_said_over_claude_cuts_it_off_and_cancels_everything(fakes, make_hub):
    rest_of_turn = asyncio.Event()

    async def script(request, brain):
        yield ReplyText("First sentence. Second sentence.")
        await fakes.wait_until(lambda: hub.speaker.played)
        yield ReplyText("A reply queued before the stop.")
        await rest_of_turn.wait()
        yield ReplyText("A reply from after the stop.")
        yield fakes.DONE

    hub = make_hub(fakes.Brain(script), barge_in=True)
    hub.speaker.play_s = LONG_PLAY_S
    async with hub:
        hub.hearing.hear("Claude, read me something.")
        await fakes.wait_until(lambda: hub.speaker.played and hub.parts.kernel.pending_count == 1)
        hub.hearing.hear("Stop.")  # no wake phrase needed over Claude
        await fakes.wait_until(lambda: hub.brain.interrupt_count == 1)
        hub.speaker.play_s = SHORT_PLAY_S
        rest_of_turn.set()
        await fakes.wait_until(lambda: "turn done" in hub.status_text)
        await fakes.wait_until(lambda: hub.parts.kernel.pending_count == 0)
        await asyncio.sleep(0.05)
    # Only the sentence being spoken was heard: not its second sentence, not
    # the reply queued before the stop, not the one after it.
    assert hub.speaker.played == [len("First sentence.")]
    assert hub.hearing.pause_count == 0
    assert "barge-in" in hub.status_text
    assert "cancelled" in hub.status_text


@pytest.mark.asyncio
async def test_stop_puts_other_agents_unreached_messages_back(fakes, make_hub):
    # Regression: a notification batched behind Claude's reply was marked
    # delivered, so a stop over the reply lost it for good.
    async def script(request, brain):
        yield ReplyText("First sentence. Second sentence.")
        hub.parts.kernel.submit(create_message("build", "The build finished."))
        yield fakes.DONE

    hub = make_hub(fakes.Brain(script), barge_in=True)
    hub.speaker.play_s = LONG_PLAY_S
    async with hub:
        hub.hearing.hear("Claude, read me something.")
        await fakes.wait_until(lambda: hub.speaker.played)
        hub.speaker.play_s = SHORT_PLAY_S
        hub.hearing.hear("Stop.")
        await fakes.wait_until(lambda: "cancelled" in hub.status_text)
        await fakes.wait_until(lambda: len(hub.speaker.played) == 2)
    assert hub.speaker.played == [len("First sentence."), len("The build finished.")]


@pytest.mark.asyncio
async def test_wake_request_over_claude_cuts_it_off_and_is_asked(fakes, make_hub):
    async def script(request, brain):
        if "story" in request:
            yield ReplyText("Once upon a time. There was a fox. The end.")
            await fakes.wait_until(lambda: hub.speaker.played)
            yield ReplyText("And that is why foxes are red.")  # queued, stale after the cut
        else:
            await asyncio.sleep(ANSWER_DELAY_S)
            yield ReplyText(f"You said: {request}")
        yield fakes.DONE

    hub = make_hub(fakes.Brain(script), barge_in=True)
    hub.speaker.play_s = LONG_PLAY_S
    async with hub:
        hub.hearing.hear("Claude, tell me a story.")
        await fakes.wait_until(lambda: hub.speaker.played and hub.parts.kernel.pending_count)
        hub.speaker.play_s = SHORT_PLAY_S
        hub.hearing.hear("Hey Claude, actually, what's the time?")
        await fakes.wait_until(lambda: len(hub.speaker.played) == 2)
    assert hub.brain.requests == ["tell me a story.", "actually, what's the time?"]
    # The rest of the story and the reply queued behind it were never spoken.
    assert hub.speaker.played == [
        len("Once upon a time."),
        len("You said: actually, what's the time?"),
    ]


@pytest.mark.asyncio
async def test_claudes_own_echo_and_side_chatter_do_not_cut_it_off(fakes, make_hub):
    async def script(request, brain):
        yield ReplyText("Claude here, so stop the timer when it beeps.")
        yield fakes.DONE

    hub = make_hub(fakes.Brain(script), barge_in=True)
    hub.speaker.play_s = 0.3
    async with hub:
        hub.hearing.hear("Claude, what do I do?")
        await fakes.wait_until(lambda: hub.speaker.played)
        # Echoes of Claude's sentence, stop and wake words included, then chatter.
        for heard in ("stop", "Claude, stop", "Claude here", "Is dinner ready yet?"):
            hub.hearing.hear(heard)
        await fakes.wait_until(lambda: hub.ducker.calls == ["duck", "restore"])
    assert hub.status_text.count("ignored: echo") == 3
    assert hub.status_text.count("ignored: no wake phrase") == 1
    assert hub.speaker.stop_count == 0
    assert hub.brain.requests == ["what do I do?"]


# Long enough to say something in it: the real tail is 2 s.
TEST_TAIL_S = 0.5


@pytest.mark.asyncio
async def test_a_quick_reply_in_the_echo_tail_reaches_claude_and_its_echo_is_logged(
    fakes, make_hub, caplog
):
    # Regression: the owner's quick follow-ups, said while Claude's last words
    # could still echo, were dropped as echo or needed a wake phrase.
    async def script(request, brain):
        yield ReplyText("Should I go ahead and delete the old logs?")
        yield fakes.DONE

    caplog.set_level(logging.INFO, logger="audiohub.loop.conversation.conversation")
    # The test replies 0.05 s into the tail, so replies count from the audio end.
    hub = make_hub(fakes.Brain(script), barge_in=True, echo_tail_s=TEST_TAIL_S, reply_after_s=0.0)
    async with hub:
        hub.hearing.hear("Claude, tidy up the logs.")
        await fakes.wait_until(lambda: hub.ducker.calls == ["duck", "restore"])
        await asyncio.sleep(ANSWER_DELAY_S)  # into the echo tail
        hub.hearing.hear("delete the old logs?", started_at=time.monotonic())
        hub.hearing.hear("Yes, go ahead.", started_at=time.monotonic())
        await fakes.wait_until(lambda: len(hub.brain.requests) == 2)
    assert hub.brain.requests == ["tidy up the logs.", "Yes, go ahead."]
    assert "delete the old logs?" in caplog.text  # the dropped echo is logged
