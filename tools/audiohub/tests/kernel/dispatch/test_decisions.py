"""Tests for strict structural parsing of Sonnet's decision JSON.

The kernel's fixed rules (order, urgent, holds, drops, condensing) are
tested in test_safeguards.py.
"""

import json

import pytest

from audiohub.kernel.dispatch import DecisionError, DecisionRequest, parse_decisions

NOW = 1_000_000.0
LONG_TEXT = " ".join(["word"] * 100)


@pytest.fixture
def request_for(make_message):
    """Build a request whose pending messages have these ids (and optional priorities)."""

    def build(pending_ids, priorities=None):
        priorities = priorities or {}
        pending = [make_message(i, priorities.get(i, "normal"), LONG_TEXT) for i in pending_ids]
        return DecisionRequest(pending, [], 80, NOW)

    return build


def reply(*entries) -> str:
    return json.dumps({"decisions": list(entries)})


def test_missing_ids_are_delivered_verbatim_in_speaking_order(request_for, entry) -> None:
    request = request_for(["m1", "m2", "m3"], {"m3": "high"})
    decisions = parse_decisions(reply(entry("m1", "deliver", "short")), request)
    assert [(d.message_id, d.action, d.text) for d in decisions] == [
        ("m3", "deliver", None),
        ("m1", "deliver", "short"),
        ("m2", "deliver", None),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"decisions": [], "extra": 1}',
        '{"decisions": {}}',
        '{"decisions": ["m1"]}',
        '{"decisions": [{"id": "m1", "action": "deliver"}]}',
        '{"decisions": [{"id": "m1", "action": "skip", "reason": "r"}]}',
        '{"decisions": [{"id": "m1", "action": "deliver", "reason": "r", "x": 1}]}',
        '{"decisions": [{"id": "m1", "action": "deliver", "reason": "r", "text": 5}]}',
        '{"decisions": [{"id": 1, "action": "deliver", "reason": "r"}]}',
        'Sure! {"decisions": []}',
        '{"decisions": []}',  # regression: the warm-up's reply held every message
        '{"decisions": []}\n{"decisions": []}',
        "[" * 5000 + "]" * 5000,
    ],
)
def test_malformed_replies_are_rejected(request_for, raw) -> None:
    with pytest.raises(DecisionError):
        parse_decisions(raw, request_for(["m1"]))


def test_duplicate_id_is_rejected(request_for, entry) -> None:
    with pytest.raises(DecisionError, match="more than once"):
        parse_decisions(reply(entry("m1", "deliver"), entry("m1", "hold")), request_for(["m1"]))


def test_decision_for_an_already_delivered_id_is_ignored_not_fatal(request_for, entry) -> None:
    # Regression: Sonnet re-decided m7 from the delivered history and the whole
    # reply was thrown away in favour of the fallback.
    raw = reply(entry("m7", "deliver"), entry("m1", "deliver", "short"))
    decisions = parse_decisions(raw, request_for(["m1"]))
    assert [(d.message_id, d.text) for d in decisions] == [("m1", "short")]


def test_a_reply_about_only_unknown_ids_is_rejected(request_for, entry) -> None:
    with pytest.raises(DecisionError, match="no decision"):
        parse_decisions(reply(entry("m7", "deliver")), request_for(["m1"]))


def test_markdown_fence_is_unwrapped(request_for, entry) -> None:
    raw = "```json\n" + reply(entry("m1", "deliver")) + "\n```"
    assert parse_decisions(raw, request_for(["m1"]))[0].action == "deliver"


@pytest.mark.parametrize(
    "decision",
    [
        {"id": "m1", "action": "deliver", "reason": "r", "text": "  "},  # blank means verbatim
        {"id": "m1", "action": "deliver", "reason": "r"},  # text key omitted
    ],
    ids=["blank", "omitted"],
)
def test_blank_or_missing_condensed_text_means_verbatim(request_for, decision) -> None:
    raw = json.dumps({"decisions": [decision]})
    assert parse_decisions(raw, request_for(["m1"]))[0].text is None
