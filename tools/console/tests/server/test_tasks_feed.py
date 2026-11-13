"""TasksFeed: a change to tasks.json publishes one `tasks` event, in display order."""

from datetime import datetime

from signal_tasks import TaskChange, set_task

from signal_console.server import EventHub
from signal_console.server.tasks_feed import TasksFeed


async def test_a_task_change_publishes_one_tasks_event(tmp_path):
    events = EventHub(tmp_path / "history.jsonl")
    feed = TasksFeed(events, tmp_path / "tasks.json", tmp_path / "usage.json")
    queue = events.subscribe()
    feed.refresh()  # the empty list
    now = datetime.now().astimezone()
    set_task(tmp_path / "tasks.json", "lo", TaskChange(name="Lo", pct=10, status="review"), now)
    set_task(tmp_path / "tasks.json", "hi", TaskChange(name="Hi", pct=90, status="building"), now)
    feed.refresh()
    feed.refresh()  # nothing changed: no second event
    published = [queue.get_nowait() for _ in range(queue.qsize())]
    assert [name for name, _ in published] == ["tasks", "tasks"]
    payload = published[-1][1]
    assert [task["id"] for task in payload["active"]] == ["hi", "lo"]
    assert payload["active"][0]["number"] == 2 and payload["overallPct"] == 50
    assert "tasks" not in {name for name, _ in events.history()}  # live only
