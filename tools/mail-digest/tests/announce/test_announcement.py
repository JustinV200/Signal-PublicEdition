"""Tests for mail_digest.announce: one capped message per run, nothing spoken twice."""

from mail_digest.announce import Announcement, compose


def _items(count):
    return [Announcement(f"due|item-{i}", f"Item {i} is due.") for i in range(count)]


def test_compose_drops_announced_keys_and_sums_up_past_the_cap():
    items = [*_items(5), Announcement("due|item-0", "Repeat.")]
    text, keys = compose(items, {"due|item-1"}, max_items=3)
    assert text.startswith("Item 0 is due. Item 2 is due. Item 3 is due. ")
    # Item 4 is summed up, and the repeat of item 0 is dropped.
    assert "1 more" in text
    assert "Item 4" not in text and "Repeat" not in text
    # Only spoken items count as announced; the summed-up one can be spoken later.
    assert keys == ("due|item-0", "due|item-2", "due|item-3")
    assert compose(_items(1), {"due|item-0"}, max_items=3) == ("", ())
