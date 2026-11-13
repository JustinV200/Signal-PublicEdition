"""Shared fixtures for camera tests: a synthetic whiteboard and marker ink on it.

`board_image` is a 1280x720 BGR board: an uneven light grey like a real board
under room light, plus camera noise. `marks` holds the marks the detection and
watcher tests share: a dark marker "HELLO", a quick word at any ink depth, the
board's frame flickering into the outer strip, and the projector's glare spot beside
the word.
Each call gets fresh noise from a seeded generator, so runs are repeatable.
"""

from collections.abc import Callable
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

BOARD_SIZE = (1280, 720)
NOISE_SIGMA = 3.0
INK_GREY = 50
# Where marks.hello writes, as (x0, y0, x1, y1). Away from where tests put a "person".
INK_REGION = (150, 300, 470, 370)
# Where marks.word writes (baseline start): clear of INK_REGION and the projections.
WORD_ORIGIN = (700, 400)
# A dark marker's ink keeps this much of the light under it.
DARK_INK_DEPTH = 0.25
# The band the board's dark frame covers when it flickers in: y from, to; and its grey.
BOARD_EDGE_ROWS = (4, 10)
BOARD_EDGE_GREY = 110
# Where marks.glare puts the projector's glare spot: just right of marks.word, so its
# halo reaches the word's last letter.
GLARE_CENTER = (760, 392)


@pytest.fixture
def board_image() -> Callable[[], np.ndarray]:
    """Factory for a fresh noisy board frame (same lighting, new noise each call)."""
    rng = np.random.default_rng(7)
    width, height = BOARD_SIZE
    # Brighter in the middle, darker at the edges, like a projector-lit room.
    columns = np.linspace(-1, 1, width)
    lighting = 205 - 30 * np.abs(columns)[None, :] - 10 * np.linspace(0, 1, height)[:, None]

    def make() -> np.ndarray:
        noisy = lighting + rng.normal(0, NOISE_SIGMA, (height, width))
        gray = np.clip(noisy, 0, 255).astype(np.uint8)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    return make


@pytest.fixture
def ink_region() -> tuple[int, int, int, int]:
    """Where marks.hello writes, as (x0, y0, x1, y1)."""
    return INK_REGION


def write_hello(image: np.ndarray) -> np.ndarray:
    """A copy with a dark marker "HELLO" in INK_REGION."""
    inked = image.copy()
    x0, _y0, _x1, y1 = INK_REGION
    grey = (INK_GREY, INK_GREY, INK_GREY)
    cv2.putText(inked, "HELLO", (x0 + 10, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 2, grey, 4)
    return inked


def write_word(image: np.ndarray, depth: float = DARK_INK_DEPTH) -> np.ndarray:
    """A copy with a quick "yes" (about 41x22 px) whose ink keeps `depth` of the light under it."""
    word = np.zeros(image.shape[:2], np.uint8)
    cv2.putText(word, "yes", WORD_ORIGIN, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
    inked = image.astype(np.float32)
    inked[word > 0] *= depth
    return inked.astype(np.uint8)


def draw_board_edge(image: np.ndarray) -> np.ndarray:
    """A copy with the board's dark frame flickering into the outer strip along the top."""
    edged = image.copy()
    top, bottom = BOARD_EDGE_ROWS
    grey = (BOARD_EDGE_GREY,) * 3
    cv2.rectangle(edged, (0, top), (edged.shape[1], bottom), grey, -1)
    return edged


@pytest.fixture
def marks(paint_glare: Callable[..., np.ndarray]) -> SimpleNamespace:
    """`marks.hello(image)`, `marks.word(image, depth=DARK_INK_DEPTH)`,
    `marks.board_edge(image)` and `marks.glare(image, core_px)` (see above)."""

    def glare(image: np.ndarray, core_px: int) -> np.ndarray:
        return paint_glare(image, GLARE_CENTER, core_px)

    return SimpleNamespace(
        hello=write_hello, word=write_word, board_edge=draw_board_edge, glare=glare
    )
