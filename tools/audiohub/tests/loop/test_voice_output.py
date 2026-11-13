"""Tests for VoiceOutput: chunking, ducking, pipelining, stop, cancellation and cues."""

import asyncio

import numpy as np
import pytest

from audiohub.audio import AudioStreamError
from audiohub.loop.voice_output import speakable_chunks


def test_speakable_chunks_clean_split_and_skip_wordless():
    chunks = speakable_chunks(["**Hello** there. How are you?", "...", "See `config.toml`."])
    assert chunks == ["Hello there.", "How are you?", "See config.toml."]


@pytest.mark.asyncio
async def test_speak_ducks_plays_every_chunk_then_restores(voice, synthesizer, speaker, ducker):
    assert await voice.speak("First sentence. Second sentence.", voice="bm_lewis") is True
    assert [text for text, _ in synthesizer.calls] == ["First sentence.", "Second sentence."]
    assert {name for _, name in synthesizer.calls} == {"bm_lewis"}
    assert speaker.played == [len("First sentence."), len("Second sentence.")]
    assert ducker.calls == ["duck", "restore"]
    assert voice.speaking is False


@pytest.mark.asyncio
async def test_a_stalled_chunk_is_skipped_and_the_rest_still_plays(voice, speaker, ducker):
    speaker.next_error = AudioStreamError("playback did not finish within 6.2s")
    assert await voice.speak("Lost sentence. Kept sentence.") is False
    assert speaker.played == [len("Kept sentence.")]
    assert ducker.calls == ["duck", "restore"]


@pytest.mark.asyncio
async def test_next_chunk_is_synthesized_while_current_one_plays(voice, synthesizer, speaker):
    speaker.play_s = 0.05
    await voice.speak("One. Two. Three.")
    # Chunk n+1 is synthesized before chunk n has finished playing.
    synth_times, play_ends = synthesizer.call_times, [end for _, end in speaker.play_spans]
    assert synth_times[1] < play_ends[0]
    assert synth_times[2] < play_ends[1]


@pytest.mark.asyncio
async def test_nothing_speakable_does_not_duck(voice, ducker, synthesizer):
    await voice.speak("   ... ")
    assert ducker.calls == []
    assert synthesizer.calls == []


@pytest.mark.asyncio
async def test_music_restored_when_synthesis_fails(voice, synthesizer, ducker):
    synthesizer.error = ValueError("Voice bm_nobody not found")
    with pytest.raises(ValueError, match="bm_nobody"):
        await voice.speak("Hello.")
    assert ducker.calls == ["duck", "restore"]
    assert voice.speaking is False


@pytest.mark.asyncio
async def test_music_restored_when_cancelled_mid_speech(voice, speaker, ducker, fakes):
    speaker.play_s = 10
    task = asyncio.create_task(voice.speak("A long sentence that never finishes."))
    await fakes.wait_until(lambda: speaker.played)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await fakes.wait_until(lambda: ducker.calls == ["duck", "restore"])


@pytest.mark.asyncio
async def test_stop_cuts_current_chunk_and_skips_the_rest(voice, speaker, ducker, fakes):
    speaker.play_s = 10
    started: list[str] = []
    task = asyncio.create_task(voice.speak_many(["One. Two. Three."], on_chunk=started.append))
    await fakes.wait_until(lambda: speaker.played)
    voice.stop()
    await asyncio.wait_for(task, 1)
    assert len(speaker.played) == 1
    assert started == ["One."]  # skipped chunks are never reported as started
    assert speaker.stop_count == 1
    assert ducker.calls == ["duck", "restore"]


@pytest.mark.asyncio
async def test_a_cue_plays_ducked_and_speech_waits_for_it(voice, speaker, ducker, fakes):
    speaker.play_s = 0.1
    cue = np.full(240, 0.2, dtype=np.float32)
    cue_task = asyncio.create_task(voice.play_cue(cue, 24000))
    await fakes.wait_until(lambda: speaker.played)
    assert voice.speaking is False  # a cue isn't speech
    # Speech asked for mid-cue waits instead of failing on the busy speaker,
    # and keeps the cue's duck rather than restoring and ducking back to back.
    assert await voice.speak("Hello.") is True
    assert await cue_task is True
    assert speaker.played == [len(cue), len("Hello.")]
    assert ducker.calls == ["duck", "restore"]
