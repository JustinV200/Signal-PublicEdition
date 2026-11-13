"""Tests for ConversationState: routing transcripts, phases and the follow-up window."""

import pytest

from audiohub.config import WakeSettings
from audiohub.loop.conversation import (
    Ask,
    Attend,
    BargeIn,
    Cancel,
    ConversationState,
    Echo,
    Ignore,
    Phase,
)

WAKE = WakeSettings(phrases=("hey claude", "claude"), require_wake=True, follow_up_s=8.0)


@pytest.fixture
def state() -> ConversationState:
    return ConversationState(WAKE)


@pytest.mark.parametrize(
    ("transcript", "route"),
    [
        ("Hey Claude, what's the weather?", Ask("what's the weather?")),
        ("hey cloud play some jazz", Ask("play some jazz")),
        ("What's the weather?", Ignore()),
        ("Hey Claude.", Attend()),
        ("Claude, stop.", Cancel()),
        ("Claude, cancel that please", Cancel()),
        ("Claude, stop the music", Ask("stop the music")),
    ],
)
def test_routes_outside_the_follow_up_window(state, transcript, route):
    assert state.route(transcript, heard_at=100.0) == route


def test_follow_up_window_accepts_requests_without_wake_phrase(state):
    state.speech_started()
    state.speech_finished(now=100.0)
    assert state.route("And tomorrow?", heard_at=107.9) == Ask("And tomorrow?")
    assert state.route("Stop.", heard_at=105.0) == Cancel()
    # The window is measured from when the user started speaking.
    assert state.route("And tomorrow?", heard_at=108.1) == Ignore()


def test_window_closes_when_a_turn_starts_and_reopens_after_speech(state):
    state.speech_finished(now=100.0)
    state.turn_started()
    assert state.route("pass the salt", heard_at=101.0) == Ignore()
    state.speech_finished(now=110.0)
    assert state.route("and after that?", heard_at=111.0) == Ask("and after that?")


def test_echo_of_claudes_last_words_is_dropped_but_a_real_yes_is_not(state):
    state.speech_finished(now=100.0, spoken_text="Shall I run git status? Please say yes or no.")
    assert state.route("Please say yes or no.", heard_at=101.0) == Echo()
    assert state.route("Yes.", heard_at=101.0) == Ask("Yes.")
    # Long after the speech, repeating Claude's words is the user talking.
    assert state.route("say yes or no", heard_at=200.0) == Ignore()


def test_wake_phrase_alone_opens_window_once_caller_says_so(state):
    assert state.route("Claude?", heard_at=10.0) == Attend()
    assert state.route("what's on today", heard_at=11.0) == Ignore()
    state.open_follow_up(now=10.5)
    assert state.route("what's on today", heard_at=11.0) == Ask("what's on today")


def test_wake_not_required_sends_everything(state):
    relaxed = ConversationState(WakeSettings(require_wake=False))
    assert relaxed.route("  Turn it up. ", heard_at=0.0) == Ask("Turn it up.")
    assert relaxed.route("Hey Claude, turn it up.", heard_at=0.0) == Ask("turn it up.")


def _speaking(sentences: list[tuple[float, str]], lag_s: float = 2.0) -> ConversationState:
    """A barge-in state in the middle of speaking these (start time, sentence) chunks."""
    state = ConversationState(WAKE, is_barge_in=True, echo_lag_s=lag_s)
    state.speech_started()
    for started_at, text in sentences:
        state.sentence_started(started_at, text)
    return state


@pytest.mark.parametrize(
    ("transcript", "route"),
    [
        ("stop", Echo()),  # Claude's own "stop", echoed
        ("Claude, stop", Echo()),
        ("Clawed, stop.", Echo()),  # Whisper mishearing Claude's own "Claude"
        ("Clod.", Echo()),
        ("I'll stop the timer, mate", Echo()),  # most of Claude's sentence
        ("Hey Claude, stop.", BargeIn(Cancel())),
        ("Stop talking", BargeIn(Cancel())),
        ("Hey Claude, what's the time?", BargeIn(Ask("what's the time?"))),
        ("Hey Claude.", BargeIn(Attend())),
        ("What's for dinner?", Ignore()),
    ],
)
def test_talking_over_claude_needs_a_stop_or_wake_phrase_and_skips_echoes(transcript, route):
    state = _speaking([(10.0, "Okay Claude, I'll stop the timer.")])
    state.open_follow_up(now=9.0)  # a window still open from before doesn't apply over Claude
    assert state.route(transcript, heard_at=11.0, heard_until=11.5) == route


def test_echo_check_covers_sentences_still_audible_through_the_output_lag():
    state = _speaking([(10.0, "Please stop here."), (14.0, "Then turn left.")], lag_s=2.0)
    # The first sentence stopped playing at 14.0, but with the 2 s lag and the
    # timing margin its echo is expected until 17.0.
    assert state.route("stop", heard_at=16.5, heard_until=17.0) == Echo()
    assert state.route("stop", heard_at=17.5, heard_until=18.0) == BargeIn(Cancel())


def test_a_late_utterance_is_checked_against_the_batch_it_was_said_over():
    # Regression: the next batch replaced the last one's window before that
    # batch's final utterance was routed, so it fell back to normal routing
    # (follow-up window open), and echoes or chatter reached the brain.
    state = _speaking([(10.0, "Here is the plan."), (12.0, "Anything else?")])
    state.speech_finished(now=15.0, spoken_text="Here is the plan. Anything else?")
    state.speech_started()  # the next batch begins while Whisper still works
    assert state.route("Anything else?", heard_at=14.1, heard_until=15.4) == Echo()
    assert state.route("Is dinner ready yet?", heard_at=13.5, heard_until=15.4) == Ignore()


def test_after_a_barge_in_routing_is_normal_and_no_follow_up_reopens():
    state = _speaking([(10.0, "Here is a long story.")])
    state.speech_interrupted(now=11.3, heard_until=11.0)
    state.open_follow_up(now=11.3)  # the barge-in was a bare "Hey Claude"
    # Begun after the barge-in utterance ended, though before it was routed.
    assert state.route("what's the time?", heard_at=11.1, heard_until=12.0) == Ask(
        "what's the time?"
    )
    # The cut sentence's echo can still arrive.
    assert state.route("a long story", heard_at=11.1, heard_until=12.0) == Echo()
    state.close_follow_up()
    state.speech_finished(now=13.0, spoken_text="Here is a long story.")
    assert state.route("and tomorrow?", heard_at=14.0) == Ignore()


def test_a_barge_in_closes_a_follow_up_window_left_open_by_the_last_batch():
    state = _speaking([(10.0, "Here is a long story.")])
    state.open_follow_up(now=9.0)  # the batch before finished just now
    state.speech_interrupted(now=11.3, heard_until=11.0)  # "stop"
    state.speech_finished(now=13.0, spoken_text="Here is a long story.")
    assert state.route("and tomorrow?", heard_at=14.0) == Ignore()


def test_phase_priority(state):
    assert state.phase is Phase.LISTENING
    state.turn_started()
    assert state.phase is Phase.THINKING
    state.speech_started()
    assert state.phase is Phase.SPEAKING
    state.speech_finished(now=0.0)
    state.turn_finished()
    state.turn_finished()  # an extra finish never goes negative
    assert state.phase is Phase.LISTENING
