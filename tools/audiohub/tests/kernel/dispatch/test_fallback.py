"""Tests for the deterministic fallback policy: priority, then FIFO, verbatim."""

from audiohub.kernel import fallback_policy


def test_fallback_orders_by_priority_then_arrival(make_message) -> None:
    pending = [
        make_message("m1", "low"),
        make_message("m2", "normal"),
        make_message("m3", "urgent"),
        make_message("m4", "normal"),
        make_message("m5", "high"),
    ]
    decisions = fallback_policy(pending)
    assert [d.message_id for d in decisions] == ["m3", "m5", "m2", "m4", "m1"]


def test_fallback_delivers_everything_verbatim(make_message) -> None:
    decisions = fallback_policy([make_message("m1"), make_message("m2", "low")])
    assert all(d.action == "deliver" and d.text is None for d in decisions)


def test_fallback_of_nothing_is_empty() -> None:
    assert fallback_policy([]) == []
