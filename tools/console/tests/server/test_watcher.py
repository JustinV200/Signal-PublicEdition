"""The status watcher notes every claim change in the feed, and a new session's turn starts over."""

import pytest
from conftest import tmp_model_files

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
    watcher = StatusWatcher(
        events,
        tmp_path,
        session=None,
        usage_path=tmp_path / "usage.json",
        model_files=tmp_model_files(tmp_path),
    )

    write_claim(tmp_path, Claim(r"\\.\pipe\a", "tok", "orchestrator", "10:00"))
    watcher.record_turn(START)
    write_claim(tmp_path, Claim(r"\\.\pipe\b", "tok", "orchestrator", "10:05"))
    watcher.record_turn(IDLE)  # the new session's first report survives the reset
    watcher.record_turn(IDLE)  # same claim: no further note

    notes = [data["text"] for name, data in events.history() if name == "note"]
    assert len(notes) == 2
    assert "10:05" in notes[1]
    states = [data for name, data in _drain(queue) if name == "state"]
    # The old session's open turn is gone; the new session's report is kept.
    assert states[-1]["orchestrator"]["turn"]["state"] == "idle"
    assert states[-1]["orchestrator"]["turn"]["lastActivityAt"] == 2000


def _drain(queue):
    return [queue.get_nowait() for _ in range(queue.qsize())]


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

    async def listening():
        return is_listening

    monkeypatch.setattr(watcher_module, "is_hub_listening", listening)
    monkeypatch.setattr(watcher_module, "find_console_hub", lambda state_dir: console_hub or None)
    monkeypatch.setattr(watcher_module, "find_hub", lambda: own_record_hub or None)
    watcher = StatusWatcher(
        EventHub(tmp_path / "history.jsonl"),
        tmp_path,
        session=None,
        usage_path=tmp_path / "usage.json",
        model_files=tmp_model_files(tmp_path),
    )

    await watcher.refresh(read_boards=False)
    voice = watcher.voice_status()
    assert (voice["running"], voice["phase"], voice["startedBy"]) == expected
