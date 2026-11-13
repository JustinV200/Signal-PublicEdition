"""Tests for the sleep / wake / status state machine, on fakes (no real monitors or tasks)."""

import subprocess
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest
from signal_displays import Monitor
from support.fakes import KEEPER_PID, PRIMARY, PROJECTOR, SIDE, make_rig

import sleepmode.control.machine as machine
from sleepmode.control import SleepModeError, SleepState, load_state, save_state
from sleepmode.lighting import Lighting, OpenRgbSession
from sleepmode.screens import BLACK_PAGE, BLACK_WINDOW, DDC_OFF, NIGHT_SKY

TONIGHT_SEED = 20261019


def test_sleep_then_wake_then_wake_again(tmp_path) -> None:
    rig = make_rig(tmp_path, monitors=(PRIMARY, PROJECTOR, SIDE))
    rig.screens.ddc_devices.add(SIDE.device_name)
    lights_off_by_then = []
    rig.screens.during_power_off = lambda: lights_off_by_then.append(list(rig.lighting.offs))

    asleep = rig.sleep_mode.sleep(wake_at="07:00")

    assert asleep.is_asleep and asleep.wake_at == datetime(2026, 10, 20, 7, 0)
    # The lights go off before any screen goes dark: a hung lighting step leaves them lit.
    assert lights_off_by_then == [[True]]
    assert rig.scheduler.scheduled == [datetime(2026, 10, 20, 7, 0)]
    assert rig.screens.powered_off == [PRIMARY.device_name, SIDE.device_name]
    assert rig.whiteboard.shown == [(TONIGHT_SEED, True)] and rig.whiteboard.starts == 0
    methods = {m.device_name: m.method for m in asleep.monitors}
    assert methods == {
        PRIMARY.device_name: BLACK_WINDOW,
        SIDE.device_name: DDC_OFF,
        PROJECTOR.device_name: NIGHT_SKY,
    }
    (options,) = rig.keeper.started
    # Only the monitor without DDC/CI gets a black window; the sky keeps the displays on.
    assert options.rects == ((0, 0, 1920, 1080),)
    assert options.keep_display_on and options.session_id == asleep.session_id
    assert load_state(rig.state_path) == asleep

    awake = rig.sleep_mode.wake()
    assert not awake.is_asleep and awake.woke_by == "request" and awake.notes == ()
    assert rig.screens.powered_on == [PRIMARY.device_name, SIDE.device_name]
    # Hidden again once the keeper is gone: its night guard may have shown it meanwhile.
    assert rig.whiteboard.hides == 2 and rig.scheduler.pending is None

    again = rig.sleep_mode.wake()
    assert not again.is_asleep and again.notes == ()
    # The lights went off with the screens and came back once: a repeat wake leaves them be.
    assert asleep.lighting == ("Fake lights off",)
    assert rig.lighting.offs == [True] and rig.lighting.restores == 1
    assert not rig.sleep_mode.status().state.is_asleep
    # Only the wake that ended a sleep had a keeper to make sure of, by pid and start time.
    assert rig.keeper.stopped == [(KEEPER_PID, 1)]


def test_whiteboard_unavailable_covers_the_projector_with_a_black_window(tmp_path) -> None:
    rig = make_rig(tmp_path)
    rig.whiteboard.is_available = False

    state = rig.sleep_mode.sleep()

    projector = next(m for m in state.monitors if m.is_projector)
    assert projector.method == BLACK_WINDOW and "whiteboard not up" in projector.detail
    # Sleep starts the daemon once (it resumes the night view itself), and only on sleep.
    assert rig.whiteboard.starts == 1 and state.notes == ()
    (options,) = rig.keeper.started
    # The keeper covers the projector itself and retries the night view (night_guard);
    # its display stays held on, so the timeout can't switch the projector off.
    assert options.rects == ((0, 0, 1920, 1080),)
    assert options.projector == (1920, 0, 1920, 1080) and options.keep_display_on
    # Waking still works, and a whiteboard that never showed the night view isn't a problem.
    assert rig.sleep_mode.wake().notes == ()
    assert rig.whiteboard.starts == 1


def test_a_whiteboard_that_wont_start_is_a_note_and_sleep_goes_on(tmp_path) -> None:
    rig = make_rig(tmp_path)
    rig.whiteboard.is_available = False
    rig.whiteboard.start_error = FileNotFoundError("uv not found")

    state = rig.sleep_mode.sleep()

    assert state.is_asleep and len(rig.keeper.started) == 1
    assert state.notes == ("Couldn't start the whiteboard: uv not found",)


def test_bad_wake_time_changes_nothing(tmp_path) -> None:
    rig = make_rig(tmp_path)
    with pytest.raises(ValueError):
        rig.sleep_mode.sleep(wake_at="half past never")
    assert rig.screens.powered_off == [] and rig.keeper.started == []
    assert not rig.state_path.exists()


def test_sleeping_again_keeps_the_wake_time_unless_given(tmp_path) -> None:
    rig = make_rig(tmp_path)
    first = rig.sleep_mode.sleep(wake_at="07:00")
    second = rig.sleep_mode.sleep(night_sky=False)
    assert second.wake_at == first.wake_at and rig.scheduler.pending == first.wake_at
    # Its lights are already off, so the first sleep's snapshot of them must be kept.
    assert rig.lighting.offs == [True, False]
    assert second.session_id != first.session_id
    assert second.keeper_pid == KEEPER_PID + 1
    # No state names the old keeper any more, so its topmost windows would outlast every wake.
    assert rig.keeper.stopped == [(KEEPER_PID, 1)]
    # No sky: the whiteboard shows a black page, and the keeper asks for the same.
    assert rig.whiteboard.shown[-1] == (TONIGHT_SEED, False)
    assert next(m for m in second.monitors if m.is_projector).method == BLACK_PAGE
    assert not rig.keeper.started[-1].night_sky
    rig.sleep_mode.sleep(wake_at="06:30")
    assert rig.scheduler.pending == datetime(2026, 10, 20, 6, 30)


def test_sleep_without_wake_time_removes_a_stale_task(tmp_path) -> None:
    rig = make_rig(tmp_path)
    rig.scheduler.pending = datetime(2026, 10, 19, 7, 0)
    assert rig.sleep_mode.sleep().wake_at is None
    assert rig.scheduler.pending is None


def test_a_hung_schtasks_is_a_note_not_an_error(tmp_path) -> None:
    rig = make_rig(tmp_path)
    rig.scheduler.error = subprocess.TimeoutExpired("schtasks", 15)
    state = rig.sleep_mode.sleep(wake_at="07:00")
    assert state.is_asleep and state.wake_at is None
    assert any("No wake time" in note for note in state.notes)
    # Nor can it make wake raise, or hold the keeper's black windows up while it hangs:
    # the state already says awake by the time schtasks runs.
    was_asleep = []
    rig.scheduler.during_cancel = lambda: was_asleep.append(load_state(rig.state_path).is_asleep)
    assert any("wake task" in note for note in rig.sleep_mode.wake().notes)
    assert was_asleep == [False]


def _press_ctrl_c() -> None:
    raise KeyboardInterrupt


def _save_failing_once_it_names_a_keeper(path: Path, state: SleepState) -> None:
    """machine's save_state, except the save that records a keeper fails (a full disk)."""
    if state.keeper_pid is not None:
        raise OSError("the disk is full")
    save_state(path, state)


@pytest.mark.parametrize("failure", ["keeper", "ctrl+c", "saving the keeper"])
def test_a_failed_sleep_wakes_everything_back_up(tmp_path, monkeypatch, failure) -> None:
    rig = make_rig(tmp_path)
    rig.sleep_mode.sleep()  # the sleep being replaced
    raised = SleepModeError
    if failure == "keeper":
        # Also how a keeper that dies straight away shows up (start_keeper raises).
        rig.keeper.fails = True
    elif failure == "ctrl+c":
        rig.screens.during_power_off = _press_ctrl_c  # while the screens are going dark
        raised = KeyboardInterrupt
    else:
        monkeypatch.setattr(machine, "save_state", _save_failing_once_it_names_a_keeper)
    with pytest.raises(raised):
        rig.sleep_mode.sleep()
    assert rig.whiteboard.hides == 1 and rig.screens.powered_on == [PRIMARY.device_name]
    assert not load_state(rig.state_path).is_asleep and rig.lighting.restores == 1
    # No state names the replaced sleep's keeper any more, nor a new one whose save failed,
    # so if either hangs on, only this ends it.
    new_keeper = [(KEEPER_PID + 1, 2)] if failure == "saving the keeper" else []
    assert rig.keeper.stopped == [*new_keeper, (KEEPER_PID, 1)]


def test_stale_keeper_cannot_wake_a_newer_sleep(tmp_path) -> None:
    rig = make_rig(tmp_path)
    old = rig.sleep_mode.sleep()
    stale_wakes = []
    # The old keeper's input wake lands while the new sleep is still darkening the screens.
    rig.screens.during_power_off = lambda: stale_wakes.append(
        rig.sleep_mode.wake(reason="input", only_session=old.session_id)
    )
    new = rig.sleep_mode.sleep()
    assert stale_wakes[0].is_asleep and rig.whiteboard.hides == 0
    assert not rig.sleep_mode.wake(reason="input", only_session=new.session_id).is_asleep


def test_wake_restores_everything_without_a_readable_state_file(tmp_path) -> None:
    rig = make_rig(tmp_path)
    rig.state_path.write_text("{not json", encoding="utf-8")
    # Even the keeper's own input wake, which only wakes its session, can't be stopped.
    state = rig.sleep_mode.wake(reason="input", only_session="unknown")
    assert not state.is_asleep
    assert rig.screens.powered_on == [PRIMARY.device_name]
    assert rig.whiteboard.hides == 1 and rig.scheduler.cancels == 1


def test_wake_powers_on_every_ddc_off_monitor_and_notes_one_that_stays_off(tmp_path) -> None:
    rig = make_rig(tmp_path, monitors=(PRIMARY, PROJECTOR, SIDE))
    rig.screens.ddc_devices.add(SIDE.device_name)
    rig.sleep_mode.sleep()
    # With the projector gone from the list, a fresh pick takes the side monitor (the first
    # non-primary display) for the projector, which would leave it off all day.
    rig.monitors.remove(PROJECTOR)
    rig.screens.refuse_power_on.update({SIDE.device_name, PRIMARY.device_name})
    notes = rig.sleep_mode.wake().notes
    assert rig.screens.powered_on == [PRIMARY.device_name, SIDE.device_name]
    # The primary never went off over DDC, so its refusal isn't news.
    assert len(notes) == 1 and "SIDE" in notes[0] and "power button" in notes[0]


def _power_on_failing(monitors: Sequence[Monitor]) -> dict[str, str]:
    raise RuntimeError("dxva2 crashed")


def test_a_rollback_whose_wake_fails_leaves_the_keeper_up(tmp_path, monkeypatch) -> None:
    rig = make_rig(tmp_path)
    monkeypatch.setattr(machine, "save_state", _save_failing_once_it_names_a_keeper)
    monkeypatch.setattr(rig.screens, "power_on", _power_on_failing)
    with pytest.raises(SleepModeError):
        rig.sleep_mode.sleep()
    # The screens may still be dark, so the keeper stays up to wake them on input.
    assert rig.keeper.stopped == []


@pytest.mark.parametrize("failure", ["raises", "hangs"])
def test_a_lighting_failure_is_a_note_and_sleep_and_wake_still_finish(tmp_path, failure) -> None:
    released = threading.Event()

    def open_session(exe_path: Path | None) -> OpenRgbSession | None:
        if failure == "hangs":
            released.wait(timeout=30)  # a server that never answers
        raise OSError("OpenRGB's server isn't up")

    lighting = Lighting(tmp_path / "sleepmode.toml", open_session=open_session, step_timeout_s=0.2)
    rig = make_rig(tmp_path, lighting=lighting)
    try:
        asleep = rig.sleep_mode.sleep()
        awake = rig.sleep_mode.wake()
    finally:
        released.set()
    assert asleep.is_asleep and len(rig.keeper.started) == 1
    assert any("OpenRGB couldn't turn the lights off" in note for note in asleep.notes)
    assert not awake.is_asleep and rig.screens.powered_on == [PRIMARY.device_name]
    assert any("OpenRGB couldn't bring the lights back" in note for note in awake.notes)
