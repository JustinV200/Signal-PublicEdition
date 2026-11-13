"""Tests for DDC power-off with black-window fallback, on a fake DDC (no real monitors)."""

import ctypes
from dataclasses import dataclass, field

import pytest
from support.fakes import PRIMARY, SIDE

from sleepmode.screens import BLACK_WINDOW, DDC_OFF, POWER_ON, DdcError, ScreenPower

OFF = 4
NO_DDC = "DDC/CI failed (error 0xc0262582)"


@dataclass
class FakeDdc:
    """A DDC bus: `refuses` handles raise `refusal` on writes, `reads` maps handle -> mode
    (missing: the read fails)."""

    refuses: set[int] = field(default_factory=set)
    refusal: Exception = field(default_factory=lambda: DdcError(NO_DDC))
    reads: dict[int, int] = field(default_factory=dict)
    writes: list[tuple[int, int]] = field(default_factory=list)

    def set_power_mode(self, hmonitor: int, value: int) -> None:
        if hmonitor in self.refuses:
            raise self.refusal
        self.writes.append((hmonitor, value))

    def read_power_mode(self, hmonitor: int) -> int:
        if hmonitor not in self.reads:
            raise DdcError("no answer")
        return self.reads[hmonitor]


def power(ddc: FakeDdc, sleeps: list[float]) -> ScreenPower:
    return ScreenPower(ddc=ddc, off_value=OFF, settle_s=2.0, sleep=sleeps.append)


@pytest.mark.parametrize(
    ("refuses", "read_back", "method", "detail"),
    [
        (False, OFF, DDC_OFF, ""),
        (False, None, BLACK_WINDOW, "couldn't be confirmed"),  # like some monitors' reads
        (False, 0, BLACK_WINDOW, "power mode 0"),
        (False, POWER_ON, BLACK_WINDOW, "back on"),  # woke on the live video signal
        (True, None, BLACK_WINDOW, "no DDC/CI"),  # refuses the write
    ],
)
def test_only_a_monitor_that_reads_back_an_off_mode_counts_as_off(
    refuses, read_back, method, detail
) -> None:
    # DDC/CI writes get no reply, so a monitor can take the power-off and stay lit.
    # Without this check it would stay bright all night behind no black window.
    ddc = FakeDdc(
        refuses={SIDE.handle} if refuses else set(),
        reads={} if read_back is None else {SIDE.handle: read_back},
    )
    sleeps: list[float] = []
    (result,) = power(ddc, sleeps).power_off([SIDE])
    assert result.method == method and detail in result.detail
    assert result.rect == (-1600, 0, 1600, 900)
    # Only an accepted write is waited on and read back.
    assert ddc.writes == ([] if refuses else [(SIDE.handle, OFF)])
    assert sleeps == ([] if refuses else [2.0])


def test_a_handle_ctypes_rejects_is_a_refusal_not_a_crash() -> None:
    # wake() must always reach every step, so no DDC failure may escape for one monitor.
    ddc = FakeDdc(refuses={PRIMARY.handle}, refusal=ctypes.ArgumentError("argument 1: bad"))
    screens = power(ddc, [])
    assert screens.power_off([PRIMARY])[0].method == BLACK_WINDOW
    assert list(screens.power_on([PRIMARY, SIDE])) == [PRIMARY.device_name]
