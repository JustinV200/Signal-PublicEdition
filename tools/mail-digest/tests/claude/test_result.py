"""Tests for mail_digest.claude.result: the output is untrusted, so only valid runs count."""

import pytest

from mail_digest.claude import ClaudeRun, clean_sentence, parse_result

ALIASES = ("personal", "alt", "school")
EMPTY_OUTPUT = {"suspicious": [], "summary": "ok"}


def _run(output=None, **overrides) -> ClaudeRun:
    event = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 0.12,
        "permission_denials": [],
        "structured_output": EMPTY_OUTPUT if output is None else output,
    }
    event.update(overrides)
    return ClaudeRun(result=event, version="2.1.301")


def test_success_keeps_only_valid_entries():
    output = {
        "suspicious": [
            {"alias": "personal", "message_id": "18c2f3a4b5d6e7f8", "sender": "a@evil.example"},
            {"alias": "personal", "message_id": "../../x", "sender": "a@evil.example"},
            {"alias": "personal", "message_id": "18c2f3a4b5d6e7f8", "sender": "Eve <a@b.co>"},
        ],
        "summary": "Added one todo.",
    }
    result = parse_result(_run(output), ALIASES)
    assert result.is_success
    assert [(s.message_id, s.sender) for s in result.suspicious] == [
        ("18c2f3a4b5d6e7f8", "a@evil.example")
    ]
    assert result.dropped == 2
    assert result.claude_version == "2.1.301"


def test_error_subtype_or_launch_error_is_a_failure_that_still_reports_denials():
    denial = {"tool_name": "Edit", "tool_input": {"file_path": "C:\\x\\AGENTS.md"}}
    result = parse_result(
        _run(subtype="error_max_budget_usd", permission_denials=[denial]), ALIASES
    )
    assert not result.is_success
    assert result.denials == ("Edit C:\\x\\AGENTS.md",)

    assert not parse_result(_run(structured_output=None), ALIASES).is_success
    timed_out = parse_result(ClaudeRun(error="claude ran past 1800 s and was killed"), ALIASES)
    assert not timed_out.is_success
    assert "1800" in timed_out.error


@pytest.mark.parametrize(
    ("sentence", "spoken"),
    [
        ("HP is overdue, see https://evil.example/x **now**", "HP is overdue, see now."),
        ("HP is due at 8 a.m. Reset it at evil.example now.", "HP is due at 8 a.m."),
        ("HP is overdue. Mail the TA at ta@evil.example.", "HP is overdue."),
        ("Your code is 482 910. HP is late.", "HP is late."),
        ("Log in at lms.example.edu", ""),  # nothing left to speak
        ("HP is due " + "very " * 40 + "soon.", "HP is due" + " very" * 22 + "."),
    ],
)
def test_spoken_items_drop_planted_sentences_and_are_capped(sentence, spoken):
    # Spoken items are built from plan lines that email may have shaped.
    assert clean_sentence(sentence) == spoken
