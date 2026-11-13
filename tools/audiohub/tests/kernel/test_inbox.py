"""Tests for the kernel Inbox: FIFO pending set and bounded delivered history."""

import pytest

from audiohub.kernel import Inbox


def test_pending_keeps_arrival_order(make_message) -> None:
    inbox = Inbox()
    for message_id in ("m3", "m1", "m2"):
        inbox.add(make_message(message_id))
    assert [m.id for m in inbox.pending()] == ["m3", "m1", "m2"]
    assert len(inbox) == 3


def test_duplicate_pending_id_is_rejected(make_message) -> None:
    inbox = Inbox()
    inbox.add(make_message("m1"))
    with pytest.raises(ValueError, match="m1"):
        inbox.add(make_message("m1"))


def test_mark_delivered_moves_message_into_history(make_message) -> None:
    inbox = Inbox()
    inbox.add(make_message("m1", text="long original"))
    record = inbox.mark_delivered("m1", "short")
    assert len(inbox) == 0
    assert record.spoken_text == "short"
    assert inbox.recent_delivered() == [record]


def test_history_is_bounded_and_drops_oldest(make_message) -> None:
    inbox = Inbox(history_limit=2)
    for message_id in ("m1", "m2", "m3"):
        inbox.add(make_message(message_id))
        inbox.mark_delivered(message_id, "x")
    assert [r.message.id for r in inbox.recent_delivered()] == ["m2", "m3"]


def test_discard_removes_without_history(make_message) -> None:
    inbox = Inbox()
    inbox.add(make_message("m1"))
    assert inbox.discard("m1").id == "m1"
    assert len(inbox) == 0 and inbox.recent_delivered() == []


def test_unknown_ids_raise_key_error() -> None:
    inbox = Inbox()
    with pytest.raises(KeyError):
        inbox.mark_delivered("nope", "x")
    with pytest.raises(KeyError):
        inbox.discard("nope")
