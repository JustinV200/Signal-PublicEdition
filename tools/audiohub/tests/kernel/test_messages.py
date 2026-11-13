"""Tests for kernel message types: ids, validation and the create_message helper."""

import time

import pytest

from audiohub.kernel import OutboundMessage, create_message
from audiohub.kernel.messages import new_message_id, word_count


def test_message_ids_are_short_and_unique() -> None:
    ids = [new_message_id() for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert all(i.startswith("m") and len(i) <= 8 for i in ids)


def test_create_message_fills_id_and_time() -> None:
    before = time.time()
    message = create_message("build-agent", "Tests passed.", "high", is_direct_reply=True)
    assert message.id.startswith("m")
    assert before <= message.created_at <= time.time()
    assert (message.source, message.priority, message.is_direct_reply) == (
        "build-agent",
        "high",
        True,
    )


def test_unknown_priority_is_rejected() -> None:
    with pytest.raises(ValueError, match="priority"):
        OutboundMessage("m1", "agent", "hi", "critical", 0.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["id", "source", "text"])
def test_blank_fields_are_rejected(field: str) -> None:
    values = {"id": "m1", "source": "agent", "text": "hi"}
    values[field] = "   "
    with pytest.raises(ValueError, match=field):
        OutboundMessage(values["id"], values["source"], values["text"], "normal", 0.0)


def test_word_count_splits_on_any_whitespace() -> None:
    assert word_count("one  two\nthree\tfour") == 4
    assert word_count("") == 0
