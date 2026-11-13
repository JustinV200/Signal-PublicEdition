"""Fixtures shared across test folders: a small life/ tree with week plans in the KB's
real layout, for the TODO view's parser, view and daemon tests, and the projector's
glare spot, for the camera's and the saves' ink tests.
"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

# The week of Monday 2026-10-19, in folder 2026-10-19-to-10-25.
WEEK_PLAN = """\
# Week plan (Mon 2026-10-19 to Sun 2026-10-25)

## Overdue
- [ ] [hist-205] Practice Quiz (was due 2026-10-15 17:00; upload late)
- [ ] [chem-120] A15 (due date TODO: verify; no mark)

## Priorities
1. [chem-120] A19 first

## CHEM 120
- [ ] [chem-120] A19 Recursion Drill (due 2026-10-19 23:59)
- [x] [chem-120] A17 Queues (due 2026-10-20)
- [ ] [chem-120] Reading video (due Fri 12:00)
### Later
- [ ] [chem-120] Midterm exam (due 2026-11-30)
- [ ] [chem-120] Check grades

## Of note
- [ ] [side-project] Poster draft (due 2026-11-06)
- [ ] [club] Pitch deck draft
- [ ] [side-project] Study group (due 2026-10-21 15:00)
"""


WritePlan = Callable[[str, str], Path]
PaintGlare = Callable[[np.ndarray, tuple[int, int], int], np.ndarray]

# The glare spot's halo dims by 1/e every this many px out from its blown-out core,
# so it reaches the board about 15-20 px out, as the real one does.
GLARE_FADE_PX = 4.0
WHITE = 255


@pytest.fixture
def life_dir(tmp_path: Path) -> Path:
    """A life/ folder holding WEEK_PLAN as this week's plan (week of Mon 2026-10-19)."""
    life = tmp_path / "life"
    _write(life, "2026-10-19-to-10-25", WEEK_PLAN)
    return life


@pytest.fixture
def write_week_plan(life_dir: Path) -> WritePlan:
    """Write a week's plan into life_dir: write_week_plan("2026-10-26-to-11-01", text) -> path."""
    return lambda week, text: _write(life_dir, week, text)


@pytest.fixture
def week_plan_text() -> str:
    """The text of this week's plan (2026-10-19-to-10-25) in life_dir."""
    return WEEK_PLAN


@pytest.fixture
def paint_glare() -> PaintGlare:
    """paint_glare(image, (x, y), core_px): a copy of `image` (grey or BGR) with the
    projector's glare spot on it, white out to `core_px` from (x, y), then fading."""
    return _paint_glare


def _paint_glare(image: np.ndarray, center: tuple[int, int], core_px: int) -> np.ndarray:
    """See paint_glare: the glare's light added to the board, saturating at white."""
    height, width = image.shape[:2]
    rows, columns = np.ogrid[:height, :width]
    distance = np.hypot(columns - center[0], rows - center[1])
    glow = np.exp(-np.maximum(distance - core_px, 0) / GLARE_FADE_PX)
    if image.ndim == 3:
        glow = glow[..., None]
    board = image.astype(np.float32)
    return (board + (WHITE - board) * glow).astype(np.uint8)


def _write(life: Path, week: str, text: str) -> Path:
    """Write a plan.md at life/terms/2026-fall/weeks/<week>/ (bytes, so endings stay as given)."""
    path = life / "terms" / "2026-fall" / "weeks" / week / "plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path
