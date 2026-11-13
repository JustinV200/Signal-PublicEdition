"""track and TodoStore: newly done items, the daily drop of old done items, and the state file."""

from datetime import date, timedelta
from pathlib import Path

from whiteboard.todo.source import parse_plan
from whiteboard.todo.view import DoneTracking, TodoStore, track

TODAY = date(2026, 10, 21)
OPEN = "- [ ] [chem-120] A22 (due 2026-10-21)\n- [ ] [chem-120] A23 (due 2026-10-22)\n"


def entries(text: str):
    return parse_plan(text, Path("plan.md"), date(2026, 10, 19))


def test_an_item_ticked_since_the_last_sync_is_newly_done_once() -> None:
    first = track(entries(OPEN), DoneTracking(), TODAY)
    ticked = entries(OPEN.replace("[ ] [chem-120] A22", "[x] [chem-120] A22"))
    second = track(ticked, first.tracking, TODAY)
    a22 = ticked[0].id
    assert first.newly_done == frozenset() and second.newly_done == {a22}
    assert second.done_ids == {a22} and second.hidden_ids == frozenset()
    # Syncing again the same day: still shown struck through, no second animation.
    third = track(ticked, second.tracking, TODAY)
    assert third.newly_done == frozenset() and third.hidden_ids == frozenset()
    # The next day's refresh drops it.
    assert track(ticked, third.tracking, TODAY + timedelta(days=1)).hidden_ids == {a22}


def test_an_item_first_seen_done_shows_today_without_animation() -> None:
    done = entries("- [x] [chem-120] A21 (due 2026-10-21)\n")
    result = track(done, DoneTracking(), TODAY)
    assert result.newly_done == frozenset() and result.hidden_ids == frozenset()
    assert result.tracking.done_since == {done[0].id: TODAY}


def test_unticking_forgets_the_done_day() -> None:
    ticked = entries(OPEN.replace("[ ] [chem-120] A22", "[x] [chem-120] A22"))
    yesterday = track(ticked, DoneTracking(), TODAY - timedelta(days=1))
    reopened = track(entries(OPEN), yesterday.tracking, TODAY)
    assert reopened.tracking.done_since == {} and reopened.hidden_ids == frozenset()
    assert ticked[0].id in reopened.tracking.open_ids


def test_store_round_trips_and_survives_a_corrupt_file(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "state" / "todo.json")
    tracking = DoneTracking({"abc": TODAY}, frozenset({"def"}))
    store.save(tracking)
    assert store.load() == tracking
    store.path.write_text('{"done_since": [1]}', encoding="utf-8")
    assert store.load() == DoneTracking()
