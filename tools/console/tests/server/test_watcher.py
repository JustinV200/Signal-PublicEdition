"""The status watcher: claim changes in the feed, the voice hub's phase and the away block."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import tmp_model_files
from signal_brief import BriefPaths, away_on

from signal_console.orchestrator import Claim, write_claim
from signal_console.server import EventHub
from signal_console.server import watcher as watcher_module
from signal_console.server.watcher import StatusWatcher
from signal_console.turns import TurnReport

START = TurnReport("start", "s1", 1.0)
IDLE = TurnReport("idle", "s2", 2.0)  # ends no turn by itself (too soon after any start)


def test_a_new_session_under_the_same_label_is_noted_and_resets_the_turn(tmp_path):
    events = EventHub(tmp_path / "history.jsonl")
    queue = events.subscribe()
    # record_turn only rebuilds the state, so no hub, board or HTTP session is touched.
    watcher = _watcher(tmp_path, events)

    write_claim(tmp_path, Claim(r"\\.\pipe\a", "tok", "orchestrator", "2026-10-22T10:00:00+00:00"))
    watcher.record_turn(START)
    just_now = datetime.now(UTC).isoformat(timespec="seconds")
    write_claim(tmp_path, Claim(r"\\.\pipe\b", "tok", "orchestrator", just_now))
    watcher.record_turn(IDLE)  # the new session's first report survives the reset
    watcher.record_turn(IDLE)  # same claim: no further note

    notes = [data["text"] for name, data in events.history() if name == "note"]
    assert len(notes) == 2
    # An age, not the raw UTC stamp, so the two sessions read differently.
    assert "days ago" in notes[0] and "linked just now" in notes[1]
    states = [data for name, data in _drain(queue) if name == "state"]
    # The old session's open turn is gone; the new session's report is kept.
    assert states[-1]["orchestrator"]["turn"]["state"] == "idle"
    assert states[-1]["orchestrator"]["turn"]["lastActivityAt"] == 2000


def _watcher(tmp_path, events):
    """A watcher on tmp files only (never the owner's brief or settings)."""
    return StatusWatcher(
        events,
        tmp_path,
        session=None,
        usage_path=tmp_path / "usage.json",
        model_files=tmp_model_files(tmp_path),
        brief_paths=_brief_paths(tmp_path),
    )


def _brief_paths(tmp_path):
    return BriefPaths(tmp_path / "brief", tmp_path / "sleep-state.json")


def _drain(queue):
    return [queue.get_nowait() for _ in range(queue.qsize())]


def _quiet_hub(monkeypatch, is_listening=False, console_hub=None, own_record_hub=None):
    """No real hub lookups: refresh() sees the hub as given."""

    async def listening():
        return is_listening

    monkeypatch.setattr(watcher_module, "is_hub_listening", listening)
    monkeypatch.setattr(watcher_module, "find_console_hub", lambda state_dir: console_hub)
    monkeypatch.setattr(watcher_module, "find_hub", lambda: own_record_hub)


# (console hub alive, hub's own record alive, port listening) -> (running, phase, startedBy)
VOICE_CASES = {
    "off": ((False, False, False), (False, "off", None)),
    "console hub loading": ((True, False, False), (True, "starting", "console")),
    "console hub listening": ((True, False, True), (True, None, "console")),
    "external hub loading": ((False, True, False), (True, "starting", "external")),
}


@pytest.mark.parametrize(("found", "expected"), VOICE_CASES.values(), ids=VOICE_CASES.keys())
async def test_voice_reads_a_live_hub_that_is_not_listening_yet_as_starting(
    tmp_path, monkeypatch, found, expected
):
    console_hub, own_record_hub, is_listening = found
    _quiet_hub(monkeypatch, is_listening, console_hub or None, own_record_hub or None)
    watcher = _watcher(tmp_path, EventHub(tmp_path / "history.jsonl"))

    await watcher.refresh(read_boards=False)
    voice = watcher.voice_status()
    assert (voice["running"], voice["phase"], voice["startedBy"]) == expected


# How long away mode runs (None: it's off) -> the state's away block: (state, an end shown),
# or None when the brief's state can't be read (the state is still published).
AWAY_CASES = {
    "here": (None, ("here", False)),
    "away with an end": (timedelta(days=1), ("away", True)),
    # The brief's 3-day default is no end the owner gave, so none is shown.
    "away with none": ("default", ("away", False)),
    "unreadable": ("unreadable", None),
}


@pytest.mark.parametrize(("away_for", "expected"), AWAY_CASES.values(), ids=AWAY_CASES.keys())
async def test_the_state_carries_the_owners_away_block(tmp_path, monkeypatch, away_for, expected):
    _quiet_hub(monkeypatch)
    events = EventHub(tmp_path / "history.jsonl")
    queue = events.subscribe()
    if away_for == "unreadable":
        # A folder where away.json should be: reading it fails with an OS error.
        _brief_paths(tmp_path).away.mkdir(parents=True)
    elif away_for is not None:
        now = datetime.now().astimezone()
        until = None if away_for == "default" else now + away_for
        away_on(_brief_paths(tmp_path), now, until)

    await _watcher(tmp_path, events).refresh(read_boards=False)

    away = [data for name, data in _drain(queue) if name == "state"][-1]["away"]
    assert (away and (away["state"], away["endsAt"] is not None)) == expected
