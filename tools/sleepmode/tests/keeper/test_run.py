"""Tests for the keeper's decisions, failing safe, and its command line."""

import pytest

import sleepmode.keeper.run as keeper_run
from sleepmode.cli import build_parser
from sleepmode.keeper import (
    EXIT,
    KEEP,
    KEEPER_ERROR,
    WAKE_LOST_STATE,
    WAKE_ON_INPUT,
    KeeperOptions,
    StateReading,
    decide,
    keeper_command,
    run_keeper,
)

MINE = StateReading(is_readable=True, is_asleep=True, session_id="mine")


@pytest.mark.parametrize(
    ("reading", "has_input", "expected"),
    [
        (MINE, False, KEEP),
        (MINE, True, WAKE_ON_INPUT),
        (StateReading(is_readable=True, is_asleep=False, session_id="mine"), True, EXIT),
        (StateReading(is_readable=True, is_asleep=True, session_id="newer"), False, EXIT),
        (StateReading(is_readable=False), False, WAKE_LOST_STATE),
        (None, False, KEEP),  # a transient read error: try again
        (None, True, WAKE_ON_INPUT),
    ],
)
def test_decide(reading: StateReading | None, has_input: bool, expected: str) -> None:
    assert decide(reading, "mine", has_input) == expected


def test_keeper_command_round_trips_through_the_cli_with_negative_x() -> None:
    options = KeeperOptions(
        "abc", ((-1600, 0, 1600, 900),), True, 5.0, projector=(1920, 0, 1920, 1080)
    )
    args = build_parser().parse_args(keeper_command(options, python="python")[3:])
    parsed = (args.session, tuple(args.blackout), args.keep_display_on, args.grace)
    assert parsed == (options.session_id, options.rects, True, 5.0)
    assert (args.projector, args.night_sky) == (options.projector, True)


def test_a_failing_keeper_lets_go_of_the_screens_then_wakes(monkeypatch) -> None:
    events: list[object] = []

    class Windows:
        def __init__(self, rects: object) -> None:
            events.append("windows up")

        def close(self) -> None:
            events.append("windows closed")

    class BrokenWatch:
        def __init__(self, grace_s: float, mouse: object) -> None:
            events.append("hooks up")

        def has_new_input(self) -> bool:
            raise OSError("GetLastInputInfo failed")

        def close(self) -> None:
            events.append("hooks closed")

    monkeypatch.setattr(keeper_run, "hold_awake", lambda keep: events.append("held"))
    monkeypatch.setattr(keeper_run, "release_awake", lambda: events.append("released"))
    monkeypatch.setattr(keeper_run, "BlackoutWindows", Windows)
    monkeypatch.setattr(keeper_run, "InputWatch", BrokenWatch)
    monkeypatch.setattr(keeper_run, "pump_messages", lambda: None)
    monkeypatch.setattr(keeper_run, "wait_for_messages", lambda timeout_s: None)
    options = KeeperOptions("mine", ((0, 0, 10, 10),), False, 5.0)

    action = run_keeper(options, lambda: MINE, lambda *wake: events.append(wake))

    # The hooks, windows and keep-awake go before the wake, so nothing stays dark while it runs.
    assert action == KEEPER_ERROR
    assert events == [
        "held",
        "windows up",
        "hooks up",
        "hooks closed",
        "windows closed",
        "released",
        ("keeper error", "mine"),
    ]
