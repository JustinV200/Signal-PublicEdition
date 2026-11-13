"""ScreenPower: turn monitors off over DDC/CI, falling back to a black window, and back on.

Turning off: every monitor gets a DDC power-off first. Only a monitor that then reads
back an off mode counts as off. One that refuses, switches itself straight back on (some
monitors wake on the live video signal), reads back anything else, or can't be read
back is marked for a black window instead. The black windows themselves are drawn by
the keeper process (sleepmode.keeper), which stays up all night.
"""

import ctypes
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from signal_displays import Monitor

from sleepmode.screens.ddc import POWER_OFF_MODES, POWER_ON
from sleepmode.screens.results import BLACK_WINDOW, DDC_OFF, MonitorResult

log = logging.getLogger(__name__)

# What a DDC call raises for one monitor: DdcError (an OSError), dxva2 missing, or a
# handle ctypes won't pass. Caught per monitor so a wake always reaches every step.
_DDC_FAILURES = (OSError, ctypes.ArgumentError)


class Ddc(Protocol):
    """DDC/CI power calls (sleepmode.screens.ddc in real use, a fake in tests)."""

    def read_power_mode(self, hmonitor: int) -> int:
        """Return VCP 0xD6, or raise OSError (DdcError when the monitor refuses)."""
        ...

    def set_power_mode(self, hmonitor: int, value: int) -> None:
        """Write VCP 0xD6, or raise OSError (DdcError when the monitor refuses)."""
        ...


@dataclass(frozen=True)
class ScreenPower:
    """Monitor power control.

    Attributes:
        ddc: The DDC/CI calls.
        off_value: The VCP 0xD6 value that turns a monitor off.
        settle_s: Seconds to wait before checking that powered-off monitors stayed off.
        sleep: time.sleep, or a fake in tests.
    """

    ddc: Ddc
    off_value: int
    settle_s: float
    sleep: Callable[[float], None] = time.sleep

    def power_off(self, monitors: Sequence[Monitor]) -> list[MonitorResult]:
        """Turn each monitor off over DDC/CI, or mark it for a black window.

        Args:
            monitors: The displays to darken (the projector already left out).

        Returns:
            One result per monitor, in order: DDC_OFF (confirmed off) or BLACK_WINDOW
            with the reason. Never raises for a monitor.
        """
        attempts = [self._try_off(monitor) for monitor in monitors]
        if any(error is None for _, error in attempts):
            self.sleep(self.settle_s)
        return [self._result(monitor, error) for monitor, error in attempts]

    def power_on(self, monitors: Sequence[Monitor]) -> dict[str, str]:
        """Send DDC power-on to each monitor. Harmless for one that's already on.

        Args:
            monitors: The displays to restore.

        Returns:
            {device_name: error} for the monitors that didn't accept it (often just
            monitors without DDC/CI, which were never powered off). Never raises for
            a monitor.
        """
        failures: dict[str, str] = {}
        for monitor in monitors:
            try:
                self.ddc.set_power_mode(monitor.handle, POWER_ON)
            except _DDC_FAILURES as error:
                failures[monitor.device_name] = str(error)
        return failures

    def _try_off(self, monitor: Monitor) -> tuple[Monitor, str | None]:
        """Send the DDC power-off; return the error text, or None if it was accepted."""
        try:
            self.ddc.set_power_mode(monitor.handle, self.off_value)
        except _DDC_FAILURES as error:
            log.info(
                "%s: no DDC/CI power-off (%s); using a black window", monitor.device_name, error
            )
            return monitor, f"no DDC/CI: {error}"
        return monitor, None

    def _result(self, monitor: Monitor, error: str | None) -> MonitorResult:
        """Check an accepted power-off stuck, and build the monitor's result."""
        if error is None:
            error = self._check_stayed_off(monitor)
        method = DDC_OFF if error is None else BLACK_WINDOW
        rect = (monitor.x, monitor.y, monitor.width, monitor.height)
        return MonitorResult(monitor.device_name, monitor.friendly_name, method, error or "", rect)

    def _check_stayed_off(self, monitor: Monitor) -> str | None:
        """Return why the monitor needs a black window after all, or None if it's off.

        DDC/CI writes get no reply, so an accepted power-off proves nothing: a monitor
        can take it and stay lit. Only a read of an MCCS off mode (2-5) counts; 0, 1 or
        anything else isn't proof. When in doubt it gets a black window, which is
        invisible over a monitor that really went off (and wake powers every monitor
        on either way).
        """
        try:
            mode = self.ddc.read_power_mode(monitor.handle)
        except _DDC_FAILURES as error:
            log.info(
                "%s: can't confirm the DDC power-off (%s); using a black window",
                monitor.device_name,
                error,
            )
            return f"the DDC/CI power-off couldn't be confirmed: {error}"
        if mode in POWER_OFF_MODES:
            return None
        if mode == POWER_ON:
            log.info("%s switched itself back on after DDC power-off", monitor.device_name)
            return "switched itself back on after the DDC/CI power-off"
        log.info("%s read back power mode %d after DDC power-off", monitor.device_name, mode)
        return f"read back power mode {mode}, not an off mode, after the DDC/CI power-off"
