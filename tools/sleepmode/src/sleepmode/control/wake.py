"""wake_up: sleep mode's wake, behind SleepMode.wake (the CLI, MCP tools, wake task and keeper).

It turns the monitors back on, takes the whiteboard out of its night view, marks the
state awake (so the keeper exits), brings the RGB lights back, removes the wake task
and makes sure the keeper is gone. Every step runs even with no readable state file,
and a step that fails becomes a note, never an error, so a wake always restores what
it can.
"""

import logging
from collections.abc import Sequence
from dataclasses import replace

from signal_displays import Monitor

from sleepmode.control.deps import SleepDeps
from sleepmode.control.state import SleepState, load_state_quietly, save_state
from sleepmode.schedule import SCHEDULER_FAILURES
from sleepmode.screens import BLACK_PAGE, DDC_OFF, NIGHT_SKY, MonitorResult, split_projector
from sleepmode.whiteboard_link import WhiteboardUnavailableError

log = logging.getLogger(__name__)


def wake_up(deps: SleepDeps, reason: str, only_session: str | None) -> SleepState:
    """Turn sleep mode off; SleepMode.wake documents the arguments and the result."""
    # TODO: not serialised against sleep(); see the TODO in SleepMode.sleep.
    previous = load_state_quietly(deps.state_path)
    is_current = previous is not None and previous.is_asleep and previous.session_id == only_session
    if only_session is not None and previous is not None and not is_current:
        log.info("ignoring a wake (%s) for an old sleep %s", reason, only_session)
        return previous
    notes: list[str] = []
    _restore_monitors(deps, previous, notes)
    has_hidden = _leave_night_view(deps, previous, notes)
    state = SleepState(
        is_asleep=False,
        session_id=previous.session_id if previous else "",
        since=previous.since if previous else None,
        night_sky=previous.night_sky if previous else True,
        monitors=previous.monitors if previous else (),
        woke_at=deps.now(),
        woke_by=reason,
        notes=tuple(notes),
    )
    _record_wake(deps, state, notes)
    try:
        # Only once the keeper has been told: slow lights or a hung schtasks mustn't hold
        # its black windows up. So a note from here is in the wake's answer (and the log)
        # but not in the saved state.
        _restore_lighting(deps, previous, notes)
        cancel_wake_task(deps, notes)
    finally:
        # Even on Ctrl+C during a slow schtasks: once the state says awake, no later wake
        # knows this keeper's pid, so this is its only backstop.
        _end_keeper(deps, previous)
        if has_hidden and previous is not None and previous.keeper_pid is not None:
            # The keeper's night guard may have asked for the night view after the hide
            # above; it's gone now, so this hide is the last word.
            _leave_night_view(deps, None, notes)
    log.info("awake (%s)%s", reason, f"; notes: {notes}" if notes else "")
    return replace(state, notes=tuple(notes))


def cancel_wake_task(deps: SleepDeps, notes: list[str]) -> None:
    """Remove the wake task if there is one; a failure (even a hung schtasks) is a note."""
    try:
        deps.scheduler.cancel()
    except SCHEDULER_FAILURES as error:
        log.warning("wake task: %s", error)
        notes.append(f"An earlier wake task may still be registered: {error}")


def _restore_lighting(deps: SleepDeps, previous: SleepState | None, notes: list[str]) -> None:
    """Bring the lights back unless the state says no sleep is on (a repeat wake).

    With no readable state it restores anyway: it can't tell whether the lights are
    off, and lights left dark all day are the worse mistake. Never raises.
    """
    if previous is not None and not previous.is_asleep:
        return
    notes.extend(deps.lighting.restore().notes)


def _record_wake(deps: SleepDeps, state: SleepState, notes: list[str]) -> None:
    """Save the awake state, so the keeper exits and takes its black windows.

    A failed save adds a note to notes instead of raising.
    """
    try:
        save_state(deps.state_path, state)
    except OSError as error:
        # The keeper can't be told. _end_keeper still ends it, and failing that it clears
        # everything on the next input.
        notes.append(
            f"Couldn't record the wake ({error}); if a screen is still black, move the mouse"
        )


def _end_keeper(deps: SleepDeps, previous: SleepState | None) -> None:
    """Make sure the sleep's keeper is gone; it normally exits within a second by itself.

    This runs even when the awake state couldn't be saved. The keeper then never hears
    of the wake and would keep its black windows up until the next input, so it gets the
    same treatment as a keeper that hangs on: stop_keeper gives it the normal wait, then
    ends it only if that pid's creation time still matches the recorded one. A reused
    pid is never touched, and a keeper with no recorded start time is only waited for.
    """
    if previous is not None and previous.keeper_pid is not None:
        deps.stop_keeper(previous.keeper_pid, previous.keeper_created)


def _restore_monitors(deps: SleepDeps, previous: SleepState | None, notes: list[str]) -> None:
    """DDC power-on for every display but the projector; note the ones that stay off."""
    try:
        monitors = deps.list_monitors()
    except OSError as error:
        notes.append(f"Couldn't list the displays to turn them on: {error}")
        return
    recorded = previous.monitors if previous is not None else ()
    failures = deps.screens.power_on(_power_on_targets(monitors, recorded, deps.projector_match))
    powered_off = {m.device_name: m for m in recorded if m.method == DDC_OFF}
    present = {monitor.device_name for monitor in monitors}
    for device, result in powered_off.items():
        if device not in present:
            notes.append(f"{result.label} has dropped off the display list; press its power button")
        elif device in failures:
            notes.append(
                f"{result.label} didn't turn back on ({failures[device]}); press its power button"
            )


def _power_on_targets(
    monitors: Sequence[Monitor], recorded: Sequence[MonitorResult], projector_match: str
) -> list[Monitor]:
    """The displays to send a DDC power-on: every one but the projector sleep recorded.

    The display list can look different at wake (a powered-off monitor may lose its
    name, or the projector may be gone), so picking the projector afresh could land on
    a monitor sleep powered off and leave it dark. Leaving out only the recorded
    projector means every monitor recorded as DDC_OFF gets its power-on. Only with no
    record of the sleep is the projector picked afresh, the way sleep picks it.
    """
    if recorded:
        projectors = {result.device_name for result in recorded if result.is_projector}
    else:
        projector, _ = split_projector(monitors, projector_match)
        projectors = {projector.device_name} if projector is not None else set()
    return [monitor for monitor in monitors if monitor.device_name not in projectors]


def _leave_night_view(deps: SleepDeps, previous: SleepState | None, notes: list[str]) -> bool:
    """Ask the whiteboard to leave the night view (a no-op for it outside the night view).

    Returns:
        False if the whiteboard couldn't be reached or refused.
    """
    try:
        deps.whiteboard.hide()
        return True
    except WhiteboardUnavailableError as error:
        log.info("whiteboard hide: %s", error)
        # Only worth telling the owner if this sleep really put the whiteboard in it.
        was_showing = (
            previous is not None
            and previous.is_asleep
            and any(m.method in (NIGHT_SKY, BLACK_PAGE) for m in previous.monitors)
        )
        if was_showing:
            notes.append(f"The whiteboard didn't leave its night view: {error}")
        return False
