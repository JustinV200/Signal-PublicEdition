"""SleepDeps: everything SleepMode touches outside its own logic, so tests can pass fakes.

The real set is built in sleepmode.wiring. Each protocol matches a real class:
ScreenPower (sleepmode.screens), NightViewClient (sleepmode.whiteboard_link),
WakeScheduler (sleepmode.schedule) and Lighting (sleepmode.lighting).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from signal_displays import Monitor

from sleepmode.keeper import KeeperOptions, KeeperProcess
from sleepmode.lighting import LightingReport
from sleepmode.screens import MonitorResult


class Screens(Protocol):
    """Monitor power control."""

    def power_off(self, monitors: Sequence[Monitor]) -> list[MonitorResult]:
        """Darken each monitor; never raises for a single monitor."""
        ...

    def power_on(self, monitors: Sequence[Monitor]) -> dict[str, str]:
        """Restore each monitor; return {device_name: error} for refusals."""
        ...


class NightView(Protocol):
    """The whiteboard's night view; both calls raise WhiteboardUnavailableError."""

    def show(self, seed: int, sky: bool) -> None:
        """Show the night view (sky) or a black page (no sky) on the projector."""
        ...

    def hide(self) -> None:
        """Go back to the view shown before the night view."""
        ...


class Scheduler(Protocol):
    """The one-shot wake task; both calls raise one of schedule.SCHEDULER_FAILURES."""

    def schedule(self, when: datetime) -> None:
        """Create or replace the wake task."""
        ...

    def cancel(self) -> bool:
        """Delete the wake task if there is one."""
        ...


class Lights(Protocol):
    """The RGB lights; neither call ever raises (failures come back as notes)."""

    def off(self, may_snapshot: bool) -> LightingReport:
        """Turn the lights off; may_snapshot False keeps an earlier sleep's snapshot."""
        ...

    def restore(self) -> LightingReport:
        """Bring the lights back to their daytime look."""
        ...


@dataclass(frozen=True)
class SleepDeps:
    """SleepMode's collaborators.

    Attributes:
        state_path: The state file (.state/state.json).
        list_monitors: Lists the displays (signal_displays.list_monitors); raises OSError.
        projector_match: The projector's name match.
        screens: Monitor power control.
        whiteboard: The night view.
        start_whiteboard: Starts the whiteboard daemon unless it's running, without
            waiting for it (whiteboard_link.start_whiteboard_if_down); True if it started
            one; raises OSError.
        scheduler: The wake task.
        lighting: The RGB lights.
        start_keeper: Starts the keeper and returns its pid and creation time; raises
            OSError, also when it dies straight away.
        stop_keeper: (pid, creation time or None) gives a keeper that was told to exit
            a few seconds, then ends it if it's still that process; never raises.
        is_alive: (pid, creation time or None) says whether that process is still
            running; with a creation time, a reused pid doesn't count.
        now: The current local time (naive).
        grace_s: Seconds of ignored input after sleep starts.
    """

    state_path: Path
    list_monitors: Callable[[], list[Monitor]]
    projector_match: str
    screens: Screens
    whiteboard: NightView
    start_whiteboard: Callable[[], bool]
    scheduler: Scheduler
    lighting: Lights
    start_keeper: Callable[[KeeperOptions], KeeperProcess]
    stop_keeper: Callable[[int, int | None], None]
    is_alive: Callable[[int, int | None], bool]
    now: Callable[[], datetime]
    grace_s: float
