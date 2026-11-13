"""The kept history survives a server restart with the same event ids (the page dedupes by id)."""

from signal_console.server import EventHub
from signal_console.server.events import COMPACT_AT_LINES, HISTORY_LIMIT, new_event_id


def test_history_reloads_from_disk_with_the_same_ids(tmp_path):
    path = tmp_path / "history.jsonl"
    before = EventHub(path)
    # Enough to make the file compact once, so the rewritten lines are reloaded too.
    for number in range(COMPACT_AT_LINES + 1):
        before.publish("message", {"id": new_event_id(), "role": "user", "text": str(number)})
    before.publish("state", {"busy": True})  # Live only: never kept or replayed.

    after = EventHub(path)  # A restarted server.

    assert len(after.history()) == HISTORY_LIMIT
    assert after.history() == before.history()
