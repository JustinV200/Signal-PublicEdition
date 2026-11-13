"""Board-fit requests shared by `whiteboard fit` and the board_fit MCP tool.

One place maps a fit mode (or a manual quad) to the daemon call, and turns a
flat list of eight numbers into the quad POST /api/fit expects.
"""

from collections.abc import Sequence
from typing import Any, Literal

from whiteboard.daemon_client.http_api import DaemonApi

FitMode = Literal["auto", "show", "clear"]
FIT_MODES: tuple[FitMode, ...] = ("auto", "show", "clear")
QUAD_NUMBER_COUNT = 8


def quad_from_numbers(numbers: Sequence[float]) -> list[list[float]]:
    """Turn [x1, y1, ..., x4, y4] into [[x1, y1], ..., [x4, y4]] (TL, TR, BR, BL).

    Args:
        numbers: The corners in projector pixels, clockwise from the top-left.

    Returns:
        Four [x, y] pairs.

    Raises:
        ValueError: Not exactly eight numbers.
    """
    if len(numbers) != QUAD_NUMBER_COUNT:
        raise ValueError("quad needs exactly 8 numbers: x1,y1,x2,y2,x3,y3,x4,y4 (TL, TR, BR, BL)")
    values = [float(number) for number in numbers]
    return [values[index : index + 2] for index in range(0, QUAD_NUMBER_COUNT, 2)]


def send_fit(api: DaemonApi, mode: FitMode, quad: list[list[float]] | None) -> dict[str, Any]:
    """Run one fit request: a manual quad if given, otherwise the mode.

    Args:
        api: The daemon client.
        mode: "auto" (re-detect), "show" (project the outline) or "clear" (remove the fit).
        quad: Manual corners from quad_from_numbers; overrides mode.

    Returns:
        The daemon's JSON answer.

    Raises:
        ValueError: An unknown mode.
    """
    if quad is not None:
        return api.fit_quad(quad)
    if mode == "auto":
        return api.fit_auto()
    if mode == "show":
        return api.fit_show()
    if mode == "clear":
        return api.fit_quad(None)
    raise ValueError(f"fit mode must be one of {', '.join(FIT_MODES)}, got {mode!r}")
