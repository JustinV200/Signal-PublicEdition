"""Tests for the kernel's fixed rules on Sonnet's decisions (dispatch/safeguards.py)."""

import logging

import pytest

from audiohub.kernel import Decision, DeliveredRecord
from audiohub.kernel.dispatch import DecisionRequest
from audiohub.kernel.dispatch.safeguards import apply_safeguards, fast_path_decisions

NOW = 1_000_000.0
LONG_TEXT = " ".join(f"word{i}" for i in range(100))
CODE_TEXT = "Error in src/app/main.py: KeyError {'user_id'} at line 42; see /var/log/app.log"


def request(pending, history=()):
    return DecisionRequest(tuple(pending), tuple(history), 80, NOW)


def delivered(message) -> DeliveredRecord:
    return DeliveredRecord(message, message.text)


def outcome(decisions) -> list[tuple[str, str, str | None]]:
    return [(d.message_id, d.action, d.text) for d in decisions]


@pytest.mark.parametrize(
    "decision",
    [
        Decision("m1", "hold", None, "user busy"),
        Decision("m1", "drop", None, "duplicate of m9"),
        Decision("m1", "deliver", "shorter", "condensed"),
    ],
    ids=["hold", "drop", "condense"],
)
def test_urgent_is_always_delivered_verbatim(make_message, decision) -> None:
    urgent = make_message("m1", "urgent", LONG_TEXT)
    twin = make_message("m9", "normal", LONG_TEXT)
    [result] = apply_safeguards([decision], request([urgent], [delivered(twin)]))
    assert (result.action, result.text) == ("deliver", None)


def test_holds_are_delivered_verbatim(make_message) -> None:
    # Regression: a hold delayed a message by a whole re-check interval while
    # the user was free to hear it.
    decisions = [Decision("m1", "hold", None, "later")]
    [result] = apply_safeguards(decisions, request([make_message("m1", "low")]))
    assert (result.action, result.text) == ("deliver", None)


def test_code_sets_speaking_order_not_sonnet(make_message) -> None:
    # Regression: Sonnet could reorder a reply's parts or bury an urgent message.
    pending = [
        make_message("m1", "low"),
        make_message("m2", "urgent"),
        make_message("m3", "high", is_direct_reply=True),
        make_message("m4", "high", is_direct_reply=True),
    ]
    decisions = [Decision(f"m{n}", "deliver", None, "ok") for n in (4, 1, 2, 3)]
    result = apply_safeguards(decisions, request(pending))
    assert [d.message_id for d in result] == ["m3", "m4", "m2", "m1"]


SHORT = "Build finished."


@pytest.mark.parametrize(
    ("messages", "history", "expected"),
    [
        ([("normal", SHORT, False)], [], ["m1"]),
        ([("normal", SHORT, False)], [SHORT], None),
        (
            [("high", SHORT, True), ("urgent", LONG_TEXT, False), ("high", SHORT, True)],
            [],
            ["m1", "m3", "m2"],
        ),
        ([("high", SHORT, True), ("normal", SHORT, False)], [], None),
        ([("high", LONG_TEXT, True)], [], None),
        ([("high", CODE_TEXT, True)], [], None),
    ],
    ids=["lone-note", "lone-repeat", "replies-and-urgent", "reply-and-note", "long", "code"],
)
def test_fast_path(make_message, messages, history, expected) -> None:
    pending = [
        make_message(f"m{n}", priority, text, is_direct_reply=is_direct)
        for n, (priority, text, is_direct) in enumerate(messages, start=1)
    ]
    heard = [delivered(make_message(f"h{n}", text=text)) for n, text in enumerate(history)]
    result = fast_path_decisions(pending, heard, 80)
    if expected is None:
        assert result is None
    else:
        assert outcome(result) == [(i, "deliver", None) for i in expected]


def test_drop_of_a_repeat_of_shown_history_stands(make_message) -> None:
    earlier = make_message("m1", text="Tests passed: 214 of 214.")
    repeat = make_message("m2", text="Tests passed:  214 of 214")
    decisions = [Decision("m2", "drop", None, "duplicate of m1")]
    [result] = apply_safeguards(decisions, request([repeat], [delivered(earlier)]))
    assert result.action == "drop"


def test_drop_of_a_duplicate_delivered_in_the_same_batch_stands(make_message) -> None:
    pending = [make_message("m1"), make_message("m2")]
    decisions = [Decision("m1", "deliver", None, "ok"), Decision("m2", "drop", None, "same as m1")]
    assert outcome(apply_safeguards(decisions, request(pending)))[1][1] == "drop"


@pytest.mark.parametrize(
    "reason",
    ["duplicate", "duplicate of m2", "duplicate of m12", "duplicate of m3", "duplicate of m4"],
    ids=["no-id", "only-itself", "id-prefix", "held-message", "different-text"],
)
def test_unjustified_drop_becomes_verbatim_delivery(make_message, reason) -> None:
    history = [
        delivered(make_message("m1", text="hello there")),
        delivered(make_message("m4", text="Deploy finished.")),
    ]
    pending = [make_message("m2", text="hello there"), make_message("m3", text="hello there")]
    decisions = [Decision("m3", "hold", None, "later"), Decision("m2", "drop", None, reason)]
    result = apply_safeguards(decisions, request(pending, history))
    assert ("m2", "deliver", None) in outcome(result)


def test_drop_may_only_point_at_history_sonnet_was_shown(make_message) -> None:
    oldest = delivered(make_message("m0", text="hello there"))
    newer = [delivered(make_message(f"h{i}", text=f"note {i}")) for i in range(10)]
    decisions = [Decision("m2", "drop", None, "duplicate of m0")]
    [result] = apply_safeguards(decisions, request([make_message("m2")], [oldest, *newer]))
    assert result.action == "deliver"


def test_condensing_a_long_message_is_accepted(make_message) -> None:
    decisions = [Decision("m1", "deliver", "Short summary.", "condensed")]
    [result] = apply_safeguards(decisions, request([make_message("m1", text=LONG_TEXT)]))
    assert result.text == "Short summary."


def test_condensing_short_code_heavy_text_is_accepted(make_message) -> None:
    decisions = [Decision("m1", "deliver", "A KeyError in the main app.", "condensed")]
    [result] = apply_safeguards(decisions, request([make_message("m1", text=CODE_TEXT)]))
    assert result.text == "A KeyError in the main app."


@pytest.mark.parametrize(
    ("original", "condensed"),
    [
        ("Your meeting with Sam is at 3 pm.", "Meeting at 3."),
        (LONG_TEXT, LONG_TEXT + " and more"),
    ],
    ids=["not-excessive", "not-shorter"],
)
def test_condensing_is_refused_otherwise(make_message, original, condensed) -> None:
    message = make_message("m1", text=original)
    decisions = [Decision("m1", "deliver", condensed, "condensed")]
    [result] = apply_safeguards(decisions, request([message]))
    assert (result.action, result.text) == ("deliver", None)


def test_accepted_condensed_text_over_the_limit_is_kept_and_logged(make_message, caplog) -> None:
    condensed = " ".join(["word"] * 90)
    decisions = [Decision("m1", "deliver", condensed, "condensed")]
    with caplog.at_level(logging.WARNING):
        [result] = apply_safeguards(decisions, request([make_message("m1", text=LONG_TEXT * 2)]))
    assert result.text == condensed
    assert "90 words" in caplog.text
