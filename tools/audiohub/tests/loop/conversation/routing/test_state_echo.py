"""Barge-in's echo tail in ConversationState: replies get through once heard, echoes don't."""

import dataclasses

import pytest

from audiohub.config import AudioSettings, WakeSettings
from audiohub.loop.conversation import Ask, Cancel, ConversationState, Echo, Ignore

WAKE = WakeSettings(phrases=("hey claude", "claude"), require_wake=True, follow_up_s=8.0)
GLASSES = AudioSettings(barge_in=True, echo_tail_s=2.0, reply_after_s=1.3)
HALF_DUPLEX = dataclasses.replace(GLASSES, barge_in=False)
LAG_S = GLASSES.echo_tail_s
AUDIO_END = 20.0
# The old wording, which says "yes" itself: the hard case for the echo checks.
LOGS_QUESTION = "Should I go ahead and delete the old logs?"


def _played_out(*sentences: str, audio=GLASSES, wake=WAKE) -> ConversationState:
    """A state that played these sentences, one a second from 10.0, until AUDIO_END."""
    state = ConversationState(
        wake,
        is_barge_in=audio.barge_in,
        echo_lag_s=audio.echo_tail_s,
        reply_after_s=audio.reply_after_s,
    )
    state.speech_started()
    for index, text in enumerate(sentences):
        state.sentence_started(10.0 + index, text)
    state.speech_audio_ended(AUDIO_END)
    return state


def _at(state: ConversationState, transcript: str, offset_s: float = 1.5, **options):
    """Route an utterance begun `offset_s` after the audio ended: by default a reply in the tail."""
    heard_at = AUDIO_END + offset_s
    return state.route(transcript, heard_at=heard_at, heard_until=heard_at + 0.5, **options)


@pytest.mark.parametrize(
    ("spoken", "heard", "offset_s", "is_ask"),
    [
        # Regression: a reply made of words anywhere in Claude's last few sentences
        # was dropped as echo, and any other reply in the tail needed a wake phrase.
        ("Yes, I can do that one, or go ahead with the other. Which one?", "go ahead", 1.5, True),
        # Regression: before the user could even hear Claude stop, a misheard
        # or cut-short echo of its last words was taken for a reply.
        ("Done.", "Dun.", 1.2, False),
        ("I've set a timer for ten minutes.", "make it fifteen minutes", 1.9, True),
    ],
)
def test_only_what_begins_once_the_user_heard_claude_stop_is_a_reply(
    spoken, heard, offset_s, is_ask
):
    route = _at(_played_out(spoken), heard, offset_s)
    assert isinstance(route, Ask) is is_ask


def test_with_no_follow_up_time_a_reply_in_the_tail_needs_the_wake_phrase():
    # Regression: follow_up_s = 0 still let replies in the echo tail through.
    state = _played_out("Done.", wake=dataclasses.replace(WAKE, follow_up_s=0.0))
    assert _at(state, "make it fifteen minutes") == Ignore()


@pytest.mark.parametrize(
    ("spoken", "heard", "route"),
    [
        ("Claude here: I'll stop the timer when it beeps.", "stop", Echo()),  # Claude's own
        # A real one is followed without cutting in: Claude has stopped.
        ("The kettle is on.", "Stop.", Cancel()),
        ("The kettle is on.", "Hey Claude, what's the time?", Ask("what's the time?")),
    ],
)
def test_a_stop_or_wake_request_in_the_tail_is_followed_unless_it_is_claudes_own(
    spoken, heard, route
):
    assert _at(_played_out(spoken), heard) == route


@pytest.mark.parametrize(
    ("spoken", "heard", "audio", "route"),
    [
        # Regression: replies made mostly of Claude's words were dropped as
        # echo after the tail, though its voice no longer reaches the live mic.
        ("Should I do that one?", "yeah do that one", GLASSES, Ask("yeah do that one")),
        # Regression: one word added to Claude's ending was still dropped.
        (LOGS_QUESTION, "Please delete the old logs.", GLASSES, Ask("Please delete the old logs.")),
        # Claude's exact last words are still dropped; half-duplex keeps the old check.
        (LOGS_QUESTION, "delete the old logs", GLASSES, Echo()),
        ("Should I do that one?", "yeah do that one", HALF_DUPLEX, Echo()),
    ],
)
def test_after_the_tail_a_reply_is_an_echo_only_as_claudes_exact_last_words(
    spoken, heard, audio, route
):
    state = _played_out(spoken, audio=audio)
    state.speech_finished(now=AUDIO_END + LAG_S, spoken_text=spoken)
    assert _at(state, heard, LAG_S + 0.6) == route


def test_the_follow_up_window_lasts_past_the_tail_and_a_tail_request_shuts_it():
    state = _played_out("Done.")
    assert state.is_in_follow_up(AUDIO_END + LAG_S + WAKE.follow_up_s)
    state.turn_started()  # a reply heard in the tail went to Claude
    state.speech_finished(now=AUDIO_END + LAG_S, spoken_text="Done.")
    assert state.route("pass the salt", heard_at=AUDIO_END + 3.0) == Ignore()


@pytest.mark.parametrize("audio", [GLASSES, HALF_DUPLEX])
@pytest.mark.parametrize(
    ("is_thinking", "next_batch_s", "said_s", "route", "closed_after"),
    [
        (True, 6.0, 4.0, Ignore(), False),
        (False, 6.0, 4.0, Ask("and the dog"), False),
        # The window had expired (at 10.0) when this batch's audio ended, yet
        # what was begun in its last moments still counts.
        (False, 11.0, 9.5, Ask("and the dog"), False),
        # ...unless a request was accepted since: that closes the kept window too.
        (False, 11.0, 9.5, Ignore(), True),
    ],
)
def test_what_was_said_before_a_batch_is_a_follow_up_only_if_a_window_was_open_then(
    audio, is_thinking, next_batch_s, said_s, route, closed_after
):
    # Regression: the window an audio end opens had no start, so chatter said
    # while Claude was thinking, routed late, reached Claude.
    state = _played_out("Done.", audio=audio)  # its window opens at AUDIO_END
    state.speech_finished(now=AUDIO_END + LAG_S, spoken_text="Done.")
    if is_thinking:
        state.turn_started()
    state.speech_started()
    state.sentence_started(AUDIO_END + next_batch_s, "Also, a new email arrived.")
    state.speech_audio_ended(AUDIO_END + next_batch_s + 1.0)
    if closed_after:
        state.turn_started()
    assert _at(state, "and the dog", said_s) == route  # begun before this batch, routed now


def test_a_tail_utterance_routed_after_the_next_batch_began_is_checked_against_its_batch():
    state = _played_out("Should I do it?")
    state.speech_finished(now=AUDIO_END + LAG_S, spoken_text="Should I do it?")
    state.speech_started()  # the next batch begins while Whisper still works
    state.sentence_started(AUDIO_END + 2.5, "Also, a new email arrived.")
    assert _at(state, "do it?") == Echo()
    assert _at(state, "Yes please.") == Ask("Yes please.")
