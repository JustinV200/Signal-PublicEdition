"""Turn state from out-of-order hook reports: ordering rules, staleness and agent counts."""

import pytest

from signal_console.turns import TurnReport, TurnTracker
from signal_console.turns.tracker import STALE_AFTER_S

START_AT = 1_000.0


def _report(phase, offset_s, background_tasks=None):
    return TurnReport(phase, "s1", START_AT + offset_s, background_tasks)


# (reports as (phase, seconds after START_AT), seconds after START_AT to check at, expected state)
TURN_CASES = {
    "nothing heard yet": ([], 0, "unknown"),
    "start": ([("start", 0)], 30, "working"),
    "start then end": ([("start", 0), ("end", 30)], 31, "idle"),
    "a late start after the end is ignored": (
        [("start", 0), ("end", 30), ("start", 20)],
        31,
        "idle",
    ),
    "a start within 2 s of the end is folded into it": (
        [("start", 0), ("end", 30), ("start", 31.5)],
        32,
        "idle",
    ),
    "an end landing just before its own late start still closes it": (
        [("start", 31), ("end", 30)],
        32,
        "idle",
    ),
    "an end stamped well before the open start leaves it open": (
        [("start", 31), ("end", 10)],
        32,
        "working",
    ),
    "idle_prompt on a turn under 60 s old is ignored": (
        [("start", 0), ("idle", 30)],
        31,
        "working",
    ),
    "idle_prompt on an older turn ends it": ([("start", 0), ("idle", 61)], 62, "idle"),
    "silence just short of the stale limit": ([("start", 0)], STALE_AFTER_S - 1, "working"),
    "stale after silence": ([("start", 0)], STALE_AFTER_S, "stale"),
}


@pytest.mark.parametrize(("reports", "check_at", "expected"), TURN_CASES.values(), ids=TURN_CASES)
def test_turn_state_follows_the_ordering_rules(reports, check_at, expected):
    tracker = TurnTracker()
    for phase, offset_s in reports:
        tracker.record(_report(phase, offset_s))

    assert tracker.status(START_AT + check_at, usage_agents=0)["state"] == expected


def test_usage_activity_keeps_a_turn_from_going_stale():
    tracker = TurnTracker()
    tracker.record(_report("start", 0))
    tracker.note_activity(START_AT + 300)  # a subagent hook, through usage.json

    assert tracker.status(START_AT + STALE_AFTER_S, usage_agents=1)["state"] == "working"


@pytest.mark.parametrize(
    ("usage_agents", "background_tasks", "expected"),
    [
        (3, 2, {"state": "agents", "agents": 2, "agentsUnsure": True}),
        (2, 2, {"state": "agents", "agents": 2, "agentsUnsure": False}),
    ],
)
def test_agents_after_a_turn_show_the_lower_count_when_sources_disagree(
    usage_agents, background_tasks, expected
):
    tracker = TurnTracker()
    tracker.record(_report("start", 0))
    tracker.record(_report("end", 30, background_tasks))

    status = tracker.status(START_AT + 31, usage_agents)
    assert {key: status[key] for key in expected} == expected
