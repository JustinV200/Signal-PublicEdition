"""Public API of sleepmode.screens: monitor power over DDC/CI, results, and the projector split."""

from sleepmode.screens import ddc
from sleepmode.screens.ddc import POWER_MODE_VCP, POWER_ON, DdcError
from sleepmode.screens.power import Ddc, ScreenPower
from sleepmode.screens.projector import split_projector
from sleepmode.screens.results import (
    BLACK_PAGE,
    BLACK_WINDOW,
    DDC_OFF,
    METHODS,
    NIGHT_SKY,
    MonitorResult,
)

__all__ = [
    "BLACK_PAGE",
    "BLACK_WINDOW",
    "DDC_OFF",
    "METHODS",
    "NIGHT_SKY",
    "POWER_MODE_VCP",
    "POWER_ON",
    "Ddc",
    "DdcError",
    "MonitorResult",
    "ScreenPower",
    "ddc",
    "split_projector",
]
