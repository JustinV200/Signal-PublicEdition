"""The board page's display modes and what they flash: calibration markers and highlights.

Plain data the BoardController (controller.py) pushes to the pages, and that the
/api/mode and /api/highlight request parsers (server/requests.py) build.
"""

from dataclasses import dataclass

# normal: the scene. blank: all black, for a clean camera read of the owner's ink.
# pattern: only calibration markers, in projector pixels. fit: the scene plus an
# outline of the board quad (or the whole projector), to check the board fit.
NORMAL_MODE = "normal"
PATTERN_MODE = "pattern"
DISPLAY_MODES: tuple[str, ...] = (NORMAL_MODE, "blank", PATTERN_MODE, "fit")


@dataclass(frozen=True)
class Marker:
    """One calibration marker image shown in pattern mode, placed in projector pixels.

    `url` is a `data:image/...` URL or a same-origin path such as `/files?path=...`.
    """

    url: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Highlight:
    """A bright box flashed on the board for a few seconds, in stage pixels."""

    x: float
    y: float
    w: float
    h: float
    seconds: float
