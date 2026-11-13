"""Tests for the dispatcher request rendering."""

import json

from audiohub.kernel import DISPATCHER_PROMPT, DeliveredRecord
from audiohub.kernel.dispatch import DecisionRequest, render_request

NOW = 1_000_000.0


def payload(request: DecisionRequest) -> dict:
    return json.loads(render_request(request).split("\n", 1)[1])


def test_request_lists_pending_with_all_fields(make_message) -> None:
    message = make_message("m7", "urgent", "May I push to main?", "claude", 12.4)
    data = payload(DecisionRequest([message], [], 80, NOW))
    assert data["max_spoken_words"] == 80
    assert data["pending"] == [
        {
            "id": "m7",
            "source": "claude",
            "priority": "urgent",
            "age_s": 12,
            "words": 5,
            "text": "May I push to main?",
        }
    ]


def test_history_is_cut_to_recent_items_and_words(make_message) -> None:
    long_text = " ".join(f"w{i}" for i in range(50))
    history = [
        DeliveredRecord(make_message(f"m{i}"), long_text, delivered_at=NOW - 5) for i in range(15)
    ]
    data = payload(DecisionRequest([make_message("m99")], history, 80, NOW))
    shown = data["recently_delivered"]
    assert [h["id"] for h in shown] == [f"m{i}" for i in range(5, 15)]
    assert shown[0]["text"].endswith(" ...")
    assert len(shown[0]["text"].split()) == 31  # 30 words plus the cut mark
    assert shown[0]["age_s"] == 5


def test_age_is_never_negative(make_message) -> None:
    data = payload(DecisionRequest([make_message("m1", age_s=-3)], [], 80, NOW))
    assert data["pending"][0]["age_s"] == 0


def test_system_prompt_states_the_json_contract() -> None:
    for phrase in ('"decisions"', "every pending id exactly once"):
        assert phrase in DISPATCHER_PROMPT
