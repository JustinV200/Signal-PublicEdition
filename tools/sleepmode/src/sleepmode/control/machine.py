"""SleepMode: the sleep / wake / status state machine behind the CLI and the MCP tools.

Sleep first records its new session, so the keeper of an earlier sleep can't wake
it. Then it sets or keeps the wake task, turns the RGB lights off, darkens every
display but the projector (DDC/CI power-off, else a black window), asks the
whiteboard for its night view (else a black window on the projector too, and starts
the whiteboard daemon if it's down, which shows the night view once it's up), records
the state, and starts the keeper. If anything fails after the session is recorded, it wakes
everything back up and ends any keeper it started, so no screen is left dark without
a keeper to wake it, and no keeper is left up that no state names. Wake
(control.wake) undoes all of it and is safe to run any number of times, with or
without a readable state file. Nothing here ever sleeps, hibernates or logs off the PC.
"""

import logging
import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from signal_displays import Monitor

from sleepmode.control.deps import SleepDeps
from sleepmode.control.projector_step import darken_projector
from sleepmode.control.state import (
    SleepState,
    StateFileError,
    load_state,
    load_state_quietly,
    save_state,
)
from sleepmode.control.wake import cancel_wake_task, wake_up
from sleepmode.keeper import KeeperOptions, KeeperProcess
from sleepmode.schedule import SCHEDULER_FAILURES, parse_wake_time
from sleepmode.screens import BLACK_WINDOW, MonitorResult, split_projector

log = logging.getLogger(__name__)


class SleepModeError(RuntimeError):
    """Sleep mode couldn't do what was asked (the message says what to do)."""


@dataclass(frozen=True)
class SleepStatus:
    """status()'s answer: the recorded state, and whether its keeper is really running."""

    state: SleepState | None
    is_keeper_running: bool


class SleepMode:
    """Turns sleep mode on and off."""

    def __init__(self, deps: SleepDeps) -> None:
        """Wire the state machine to its collaborators (real ones from sleepmode.wiring)."""
        self._deps = deps

    def sleep(self, wake_at: str | None = None, night_sky: bool = True) -> SleepState:
        """Turn sleep mode on, or update it if it's already on.

        Args:
            wake_at: When to wake ("07:00", "7am", ISO date-time). None keeps the
                pending wake time if sleep mode is already on, else sets none.
            night_sky: Show the whiteboard's night sky; False shows black instead.

        Returns:
            The new state, with each display's result and any notes.

        Raises:
            ValueError: wake_at can't be read or has passed (nothing was changed).
            SleepModeError: The displays couldn't be listed or the state couldn't be
                saved (nothing was changed), or a later step failed or the keeper
                didn't stay up (everything is woken back up first).
        """
        # TODO: sleep and wake_up aren't serialised across processes (the MCP server
        # serialises its own calls with SleepTools' lock). A wake and a sleep at once can
        # interleave so the wake saves "awake" over this sleep, or an older sleep's save
        # lands over a newer one: the new keeper exits and its screens stay dark. Fix: an
        # exclusive lock with a timeout around both bodies (msvcrt.locking on .state/lock,
        # or a named mutex), never awaited by a keeper this sleep stops; _roll_back wakes
        # inside it, so it must be re-entrant or call a wake body that doesn't take it.
        now = self._deps.now()
        wake_time = parse_wake_time(wake_at, now) if wake_at else None
        previous = load_state_quietly(self._deps.state_path)
        monitors = self._list_monitors()
        claim = SleepState(
            is_asleep=True, session_id=uuid.uuid4().hex, since=now, night_sky=night_sky
        )
        self._claim_session(claim)
        keeper: KeeperProcess | None = None
        try:
            notes: list[str] = []
            # Before the screens go dark, so a schtasks that hangs (or is Ctrl+C'd) leaves
            # them lit, not dark with no keeper watching for input.
            scheduled_at = self._set_wake_task(wake_time, previous, now, notes)
            # Before the screens go dark too, for the same reason: a lighting step that
            # hangs past its deadlines leaves them lit, not dark with no keeper. And before
            # the keeper starts, so no input wake can restore the lights while this is
            # still turning them off. Never raises; if a later step fails, the rollback's
            # wake brings the lights back.
            lights = self._deps.lighting.off(may_snapshot=not _is_asleep(previous))
            darkened = tuple(self._darken(monitors, night_sky, now, notes))
            state = replace(
                claim,
                monitors=darkened,
                wake_at=scheduled_at,
                lighting=lights.lines,
                notes=(*notes, *lights.notes),
            )
            keeper = self._start_keeper(state)
            state = replace(state, keeper_pid=keeper.pid, keeper_created=keeper.created)
            save_state(self._deps.state_path, state)
            self._stop_replaced_keeper(previous, keeper.pid)
        except Exception as error:
            # Whatever broke, screens left dark with no keeper would lock the owner out.
            self._roll_back(previous, keeper)
            raise SleepModeError(f"couldn't start sleep mode: {error}") from error
        except BaseException:
            self._roll_back(previous, keeper)  # Ctrl+C mid-sleep: the same dark screens
            raise
        return state

    def wake(self, reason: str = "request", only_session: str | None = None) -> SleepState:
        """Turn sleep mode off: monitors on, whiteboard back, wake task gone, keeper stopped.

        Every step runs even when the state file is missing or corrupt, and a step
        that fails is logged and noted, never fatal, so this always restores what it can.

        Args:
            reason: Recorded as woke_by ("request", "schedule", "input", ...).
            only_session: Skip the wake if the state file names another sleep, or says
                awake (the keeper passes its own, so a keeper that was replaced can't wake
                a newer sleep). A state file that can't be read doesn't stop it: screens
                left dark are the worse mistake.

        Returns:
            The awake state, with notes about anything that couldn't be restored.
        """
        return wake_up(self._deps, reason, only_session)

    def status(self) -> SleepStatus:
        """The recorded state and whether its keeper is still running.

        Raises:
            SleepModeError: The state file can't be read.
        """
        try:
            state = load_state(self._deps.state_path)
        except (StateFileError, OSError) as error:
            raise SleepModeError(f"can't read sleep mode's state: {error}") from error
        if state is None or not state.is_asleep or state.keeper_pid is None:
            return SleepStatus(state, is_keeper_running=False)
        # With the start time too, a dead keeper's pid reused by another process isn't it.
        is_running = self._deps.is_alive(state.keeper_pid, state.keeper_created)
        return SleepStatus(state, is_running)

    def _claim_session(self, claim: SleepState) -> None:
        """Save the new session before anything changes, so an older keeper's input wake
        (made with its own session) sees a newer sleep and leaves it alone."""
        try:
            save_state(self._deps.state_path, claim)
        except OSError as error:
            raise SleepModeError(f"couldn't save sleep mode's state: {error}") from error

    def _roll_back(self, previous: SleepState | None, new_keeper: KeeperProcess | None) -> None:
        """Wake everything after a sleep that failed part-way (the lights included), then
        end this sleep's keeper (unless the wake failed) and the keeper of the sleep it
        was replacing if they hang on. Best effort: the sleep's own error is what gets
        reported, so a wake that fails too is only logged.

        Args:
            previous: The state before this sleep. The wake only sees what this sleep
                saved, which never names the earlier keeper, so that one is stopped here.
            new_keeper: This sleep's keeper, if it started. The saved state may not name
                it (the save after it started failed, or never ran), so it's stopped here.
        """
        try:
            # Not limited to this sleep's session: an unneeded wake is harmless, while a
            # skipped one could leave a monitor off with no keeper to wake it.
            self.wake(reason="sleep failed")
        except Exception:
            log.exception("couldn't wake everything after the failed sleep")
        else:
            # Only after a wake that went through, like wake_up: once it has saved "awake"
            # the keeper normally exits by itself, and this ends one that hangs. After a
            # wake that raised, the screens may still be dark, and the keeper is what
            # wakes them on input.
            if new_keeper is not None:
                self._deps.stop_keeper(new_keeper.pid, new_keeper.created)
        self._stop_replaced_keeper(previous, new_pid=None)

    def _list_monitors(self) -> list[Monitor]:
        try:
            return self._deps.list_monitors()
        except OSError as error:
            raise SleepModeError(f"couldn't list the displays: {error}") from error

    def _darken(
        self, monitors: list[Monitor], night_sky: bool, now: datetime, notes: list[str]
    ) -> list[MonitorResult]:
        """Power off (or black out) every display but the projector, then the projector."""
        projector, others = split_projector(monitors, self._deps.projector_match)
        results = self._deps.screens.power_off(others)
        if projector is not None:
            result, note = darken_projector(self._deps, projector, night_sky, now)
            results.append(result)
            if note is not None:
                notes.append(note)
        return results

    def _set_wake_task(
        self,
        wake_time: datetime | None,
        previous: SleepState | None,
        now: datetime,
        notes: list[str],
    ) -> datetime | None:
        """Create, keep or remove the wake task; return the wake time that's really set."""
        if wake_time is not None:
            try:
                self._deps.scheduler.schedule(wake_time)
                return wake_time
            except SCHEDULER_FAILURES as error:
                log.warning("wake task: %s", error)
                notes.append(f"No wake time is set: {error}")
                return None
        pending = previous.wake_at if previous is not None and previous.is_asleep else None
        if pending is not None and pending > now:
            return pending  # already asleep: keep the wake time that's set
        cancel_wake_task(self._deps, notes)
        return None

    def _start_keeper(self, state: SleepState) -> KeeperProcess:
        """Save the state, then start its keeper (sleep saves the keeper's pid after).

        Raises:
            OSError: The state couldn't be saved, or the keeper didn't start or stay up.
        """
        rects = tuple(
            m.rect for m in state.monitors if m.method == BLACK_WINDOW and not m.is_projector
        )
        projector = next((m.rect for m in state.monitors if m.is_projector), None)
        # The projector's display is held on whatever covers it: one the display timeout
        # switches off may need its remote to come back (see README).
        options = KeeperOptions(
            state.session_id,
            rects,
            keep_display_on=projector is not None,
            grace_s=self._deps.grace_s,
            projector=projector,
            night_sky=state.night_sky,
        )
        # Saved before the keeper starts: it checks that the file names its session.
        save_state(self._deps.state_path, state)
        return self._deps.start_keeper(options)

    def _stop_replaced_keeper(self, previous: SleepState | None, new_pid: int | None) -> None:
        """End the earlier sleep's keeper if it hangs on after this sleep replaced it.

        It exits by itself once it sees the new session. One that hangs would keep its
        topmost black windows up through every later wake, since no state names it.

        Args:
            previous: The state before this sleep.
            new_pid: This sleep's keeper pid, or None if it has none (the sleep failed).
        """
        if previous is None or not previous.is_asleep or previous.keeper_pid is None:
            return
        # The old pid may already have been reused by the new keeper.
        if previous.keeper_pid != new_pid:
            self._deps.stop_keeper(previous.keeper_pid, previous.keeper_created)


def _is_asleep(state: SleepState | None) -> bool:
    """True if the state says an earlier sleep is still on (so its lights are already off)."""
    return state is not None and state.is_asleep
