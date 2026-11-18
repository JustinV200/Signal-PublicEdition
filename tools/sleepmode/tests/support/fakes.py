"""Fakes for sleepmode tests: displays, screen power, the whiteboard, the scheduler, the
lights, the keeper.

Nothing here touches real monitors, Task Scheduler, the whiteboard, lights or processes.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from signal_displays import Monitor

from sleepmode.control import Lights, SleepDeps, SleepMode
from sleepmode.keeper import KeeperOptions, KeeperProcess
from sleepmode.lighting import LightingReport
from sleepmode.screens import BLACK_WINDOW, DDC_OFF, MonitorResult
from sleepmode.whiteboard_link import WhiteboardUnavailableError

PRIMARY = Monitor("\\\\.\\DISPLAY5", "PRIMARY", 0, 0, 1920, 1080, True, 1.0, handle=5)
PROJECTOR = Monitor("\\\\.\\DISPLAY1", "PROJ-1", 1920, 0, 1920, 1080, False, 1.5, handle=1)
SIDE = Monitor("\\\\.\\DISPLAY2", "SIDE", -1600, 0, 1600, 900, False, 1.0, handle=2)
NOW = datetime(2026, 10, 19, 23, 0)
KEEPER_PID = 4242  # the first fake keeper's pid; each later one gets the next


@dataclass
class FakeScreens:
    """Turns the devices in `ddc_devices` off over DDC; every other monitor gets a black window.

    `during_power_off`, if set, runs inside power_off (to land another call mid-sleep).
    """

    ddc_devices: set[str] = field(default_factory=set)
    refuse_power_on: set[str] = field(default_factory=set)
    powered_off: list[str] = field(default_factory=list)
    powered_on: list[str] = field(default_factory=list)
    during_power_off: Callable[[], object] | None = None

    def power_off(self, monitors: Sequence[Monitor]) -> list[MonitorResult]:
        if self.during_power_off is not None:
            self.during_power_off()
        results = []
        for monitor in monitors:
            self.powered_off.append(monitor.device_name)
            method = DDC_OFF if monitor.device_name in self.ddc_devices else BLACK_WINDOW
            rect = (monitor.x, monitor.y, monitor.width, monitor.height)
            results.append(
                MonitorResult(monitor.device_name, monitor.friendly_name, method, "", rect)
            )
        return results

    def power_on(self, monitors: Sequence[Monitor]) -> dict[str, str]:
        self.powered_on.extend(monitor.device_name for monitor in monitors)
        return {m.device_name: "refused" for m in monitors if m.device_name in self.refuse_power_on}


@dataclass
class FakeNightView:
    """Records show/hide calls; raises WhiteboardUnavailableError when `is_available` is False.
    A shown night view is on a page unless `has_page` is False (its kiosk closed).
    Also stands in for starting the daemon: counts `starts`, raising `start_error` if set."""

    is_available: bool = True
    has_page: bool = True
    shown: list[int] = field(default_factory=list)
    hides: int = 0
    starts: int = 0
    start_error: OSError | None = None

    def show(self, seed: int) -> None:
        if not self.is_available:
            raise WhiteboardUnavailableError("the whiteboard daemon isn't running")
        self.shown.append(seed)

    def is_showing(self) -> bool:
        if not self.is_available:
            raise WhiteboardUnavailableError("the whiteboard daemon isn't running")
        return self.has_page and bool(self.shown)

    def hide(self) -> None:
        if not self.is_available:
            raise WhiteboardUnavailableError("the whiteboard daemon isn't running")
        self.hides += 1

    def start_daemon(self) -> bool:
        if self.start_error is not None:
            raise self.start_error
        self.starts += 1
        return True


@dataclass
class FakeScheduler:
    """Holds at most one pending wake time, like the real single task. Both calls raise
    `error` when it's set. `during_cancel`, if set, runs first inside cancel."""

    pending: datetime | None = None
    error: Exception | None = None
    scheduled: list[datetime] = field(default_factory=list)
    cancels: int = 0
    during_cancel: Callable[[], object] | None = None

    def schedule(self, when: datetime) -> None:
        if self.error is not None:
            raise self.error
        self.scheduled.append(when)
        self.pending = when

    def cancel(self) -> bool:
        if self.during_cancel is not None:
            self.during_cancel()
        if self.error is not None:
            raise self.error
        self.cancels += 1
        had_task = self.pending is not None
        self.pending = None
        return had_task


@dataclass
class FakeLighting:
    """Records each off (its may_snapshot) and each restore; reports one line per off."""

    offs: list[bool] = field(default_factory=list)
    restores: int = 0

    def off(self, may_snapshot: bool) -> LightingReport:
        self.offs.append(may_snapshot)
        return LightingReport(lines=("Fake lights off",))

    def restore(self) -> LightingReport:
        self.restores += 1
        return LightingReport()


@dataclass
class FakeKeeper:
    """Records the options each keeper was started with, and each (pid, created) it was
    asked to stop. Keepers get pids from KEEPER_PID up, and their start order (1, 2, ...)
    stands in for a creation time."""

    fails: bool = False
    started: list[KeeperOptions] = field(default_factory=list)
    stopped: list[tuple[int, int | None]] = field(default_factory=list)

    def start(self, options: KeeperOptions) -> KeeperProcess:
        if self.fails:
            raise OSError("can't start python")
        self.started.append(options)
        return KeeperProcess(KEEPER_PID + len(self.started) - 1, created=len(self.started))

    def stop(self, pid: int, created: int | None) -> None:
        self.stopped.append((pid, created))


@dataclass
class Rig:
    """A SleepMode wired to fakes, plus the fakes for assertions. Changing `monitors`
    changes what the displays list from then on."""

    sleep_mode: SleepMode
    monitors: list[Monitor]
    screens: FakeScreens
    whiteboard: FakeNightView
    scheduler: FakeScheduler
    keeper: FakeKeeper
    state_path: Path
    lighting: Lights


def make_rig(
    tmp_path: Path,
    monitors: Sequence[Monitor] = (PRIMARY, PROJECTOR),
    now: datetime = NOW,
    lighting: Lights | None = None,
) -> Rig:
    """Build a SleepMode on default fakes. Tests change a fake's fields to vary its behaviour.

    `lighting` replaces the FakeLighting (e.g. with a real Lighting on fake backends).
    """
    lighting = lighting if lighting is not None else FakeLighting()
    screens = FakeScreens()
    whiteboard = FakeNightView()
    scheduler = FakeScheduler()
    keeper = FakeKeeper()
    state_path = tmp_path / "state.json"
    listed = list(monitors)
    deps = SleepDeps(
        state_path=state_path,
        list_monitors=lambda: list(listed),
        projector_match="PROJ-1",
        screens=screens,
        whiteboard=whiteboard,
        start_whiteboard=whiteboard.start_daemon,
        scheduler=scheduler,
        lighting=lighting,
        start_keeper=keeper.start,
        stop_keeper=keeper.stop,
        is_alive=lambda pid, created: (pid, created) == (KEEPER_PID, 1),
        now=lambda: now,
        grace_s=5.0,
    )
    return Rig(
        SleepMode(deps), listed, screens, whiteboard, scheduler, keeper, state_path, lighting
    )
