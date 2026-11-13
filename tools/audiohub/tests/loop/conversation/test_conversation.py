"""End-to-end tests of Conversation with a real Kernel, KernelServer and VoiceOutput.

The brain, hearing, TTS, speaker, ducker and Sonnet dispatcher are fakes, so
these run fast and offline. They cover the flows that matter: wake -> brain ->
kernel -> speech with the mic paused (barge-in off), "Claude, stop",
notifications over IPC, and music restored on shutdown.
"""

import asyncio
import functools
import json
import socket
import time

import pytest

from audiohub.brain import ReplyText
from audiohub.kernel import send_notification
from audiohub.loop import HubStartError

HOST = "127.0.0.1"


@pytest.mark.asyncio
async def test_wake_request_is_answered_aloud_with_mic_paused(fakes, make_hub):
    # Barge-in off is the old half-duplex loop: the mic is paused while Claude speaks.
    async with make_hub(barge_in=False) as hub:
        hub.hearing.hear("Hey Claude, what's the weather like in London today?")
        await fakes.wait_until(lambda: "You said" in hub.spoken)
        assert hub.brain.requests == ["what's the weather like in London today?"]
        assert hub.spoken == "You said: what's the weather like in London today?"
        assert hub.mic_paused_during_play == [True]
        await fakes.wait_until(lambda: not hub.hearing.paused)
    for label in ("ready", "listening", "heard:", "thinking:", "speaking:"):
        assert label in hub.status_text
    assert hub.ducker.calls == ["duck", "restore"]


@pytest.mark.asyncio
async def test_speech_without_wake_phrase_is_ignored_until_follow_up(fakes, make_hub):
    async with make_hub() as hub:
        hub.hearing.hear("What's the weather like?", started_at=0.0)
        hub.hearing.hear("Claude, hello.")
        await fakes.wait_until(lambda: hub.hearing.pause_count == 1 and not hub.hearing.paused)
        # Begun inside the follow-up window after Claude spoke, no wake phrase is
        # needed, but accepting a request closes the window again.
        hub.hearing.hear("And tomorrow?", started_at=time.monotonic())
        hub.hearing.hear("Pass the salt.", started_at=time.monotonic())
        await fakes.wait_until(lambda: "tomorrow" in hub.spoken)
    assert hub.brain.requests == ["hello.", "And tomorrow?"]
    assert hub.status_text.count("ignored: no wake phrase") == 2


@pytest.mark.asyncio
async def test_stop_interrupts_and_mutes_the_rest_of_the_turn(fakes, make_hub):
    rest_of_turn = asyncio.Event()

    async def slow_script(request, brain):
        await rest_of_turn.wait()
        yield ReplyText("Here is the long answer.")
        yield fakes.DONE

    async with make_hub(fakes.Brain(slow_script)) as hub:
        hub.hearing.hear("Claude, tell me everything.")
        await fakes.wait_until(lambda: "thinking" in hub.status_text)
        hub.hearing.hear("Claude, stop.")
        await fakes.wait_until(lambda: hub.brain.interrupt_count == 1)
        rest_of_turn.set()  # the SDK still flushes text after an interrupt
        await fakes.wait_until(lambda: "turn done" in hub.status_text)
        await asyncio.sleep(0.05)
    assert "long answer" not in hub.spoken
    assert "cancelled" in hub.status_text


@pytest.mark.parametrize("is_cut", [True, False])
@pytest.mark.asyncio
async def test_a_stop_leaves_the_follow_up_window_shut(fakes, make_hub, is_cut):
    # Regression: the cut batch's audio end reopened the window "stop" had
    # closed, so chatter right after the stop went to Claude. A stop once
    # Claude has finished shuts the window its speech opened.
    hub = make_hub()
    hub.speaker.play_s = 10.0 if is_cut else 0.01
    async with hub:
        hub.hearing.hear("Claude, read me a story.")
        if is_cut:  # stop while the story plays
            await fakes.wait_until(lambda: hub.speaker.played)
        else:  # or once it played out and the mic reopened
            await fakes.wait_until(lambda: hub.speaker.play_spans and not hub.hearing.paused)
        hub.hearing.hear("Claude, stop.")
        await fakes.wait_until(lambda: "cancelled" in hub.status_text and not hub.hearing.paused)
        hub.hearing.hear("Pass the salt.", started_at=time.monotonic())
        await fakes.wait_until(lambda: "ignored: no wake phrase" in hub.status_text)
    assert hub.brain.requests == ["read me a story."]


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_by", ["cancel", "ipc-shutdown"])
async def test_shutdown_mid_speech_restores_music_and_closes_everything(fakes, make_hub, stop_by):
    hub = make_hub()
    hub.speaker.play_s = 10
    async with hub:
        hub.hearing.hear("Claude, talk for a while.")
        await fakes.wait_until(lambda: hub.ducker.is_ducked and hub.speaker.played)
        if stop_by == "ipc-shutdown":
            request = {"token": hub.token_path.read_text(), "command": "shutdown"}
            reply = await asyncio.to_thread(_send_line, hub.parts.server.port, request)
            assert reply == {"ok": True}
            await asyncio.wait_for(hub.task, 5.0)  # it ends by itself, not cancelled
    await fakes.wait_until(lambda: hub.ducker.calls == ["duck", "restore"])
    assert hub.brain.closed and hub.dispatcher.closed and hub.hearing.closed


def _send_line(port: int, payload: dict) -> dict:
    """Send one request line to the hub's kernel server and return its decoded reply."""
    with socket.create_connection((HOST, port), timeout=5.0) as connection:
        connection.sendall(json.dumps(payload).encode() + b"\n")
        with connection.makefile("rb") as stream:
            return json.loads(stream.readline())


@pytest.mark.asyncio
async def test_speak_only_hub_speaks_ipc_notifications(fakes, make_hub):
    async with make_hub(listen=False) as hub:
        port = hub.parts.server.port
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(
                send_notification,
                HOST,
                port,
                "build-agent",
                "The build finished.",
                token_path=hub.token_path,
            ),
        )
        await fakes.wait_until(lambda: "The build finished." in hub.spoken)
    assert "speak-only" in hub.status_text


@pytest.mark.asyncio
async def test_taken_port_gives_a_clear_start_error(fakes, make_hub):
    with socket.socket() as holder:
        holder.bind((HOST, 0))
        holder.listen()
        hub = make_hub(listen=False, port=holder.getsockname()[1])
        with pytest.raises(HubStartError, match="another audiohub"):
            await hub.conversation.run()


@pytest.mark.asyncio
async def test_failed_speech_still_reopens_the_mic_and_restores_music(fakes, make_hub):
    async with make_hub() as hub:
        hub.synthesizer.error = RuntimeError("onnxruntime fell over")
        hub.hearing.hear("Claude, hello.")
        await fakes.wait_until(lambda: hub.hearing.pause_count == 1 and not hub.hearing.paused)
        assert hub.ducker.calls == ["duck", "restore"]
        # The hub keeps working once synthesis recovers.
        hub.synthesizer.error = None
        hub.hearing.hear("Claude, again.")
        await fakes.wait_until(lambda: "again" in hub.spoken)
