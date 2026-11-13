"""Tests for the ink diff: new strokes (even one small word, in a dim room, faint as the
lights change, or beside the projector's glare spot) and a filled box count; noise, a
small camera shift, a dim room's flickering smudges, the flickering border strip and the
glare spot's swelling halo don't."""

from collections.abc import Callable
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from whiteboard.camera.detection import ink_change
from whiteboard.config import WatcherSettings

INK_CHANGE_RATIO = WatcherSettings().ink_change_ratio
DIM_BOARD_GREY = 60
DIM_NOISE_SIGMA = 8.0
# Old faded marker just past the ink threshold: dim-room noise flips it on and off.
SMUDGE_DEPTH = 14
# The lights go down to a lamp on one side: brightness kept, left to right.
LAMP_GAIN = (0.15, 0.45)
# The lights come up: the dark frame before keeps this much of the lit one.
LIGHTS_DOWN_GAIN = 0.35
# A faint marker: its ink keeps this much of the board's brightness.
FAINT_INK_DEPTH = 0.75
# The projector's glare spot swells between captures (as in the real logs): its
# blown-out core's radius before and after.
GLARE_CORE_PX = (10, 16)
# A filled 60x60 box (a blacked-out square), far wider than a stroke: corners and grey.
FILLED_BOX = ((900, 150), (959, 209))
FILLED_BOX_GREY = 50

Frames = Callable[[], np.ndarray]
Pair = tuple[np.ndarray, np.ndarray]


def dim_room() -> Frames:
    """Factory for a dim, high-gain board with faded smudges, with spatially correlated noise."""
    rng = np.random.default_rng(7)
    width, height = 1280, 720
    columns = 1 - 0.15 * np.abs(np.linspace(-1, 1, width))
    lighting = np.repeat(DIM_BOARD_GREY * columns[None, :], height, axis=0)
    smudges = np.zeros((height, width), np.uint8)
    for y in range(120, 640, 70):
        cv2.putText(smudges, "old faded notes here", (80, y), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 255, 5)
    lighting[smudges > 0] -= SMUDGE_DEPTH

    def make() -> np.ndarray:
        noise = cv2.GaussianBlur(rng.normal(0, DIM_NOISE_SIGMA, (height, width)), (3, 3), 0)
        return np.clip(lighting + noise, 0, 255).astype(np.uint8)

    return make


def lit_by(image: np.ndarray, left_gain: float, right_gain: float) -> np.ndarray:
    """`image` under other lighting: brightness scaled from `left_gain` to `right_gain`."""
    ramp = np.linspace(left_gain, right_gain, image.shape[1], dtype=np.float32)[None, :, None]
    return (image.astype(np.float32) * ramp).clip(0, 255).astype(np.uint8)


def new_small_word_in_a_dim_room(board: Frames, marks: SimpleNamespace) -> Pair:
    dim = dim_room()
    return dim(), marks.word(dim())


def new_faint_word_as_the_lights_go_down_to_a_lamp(board: Frames, marks: SimpleNamespace) -> Pair:
    # Too faint to see unless the frames' brightness is matched, and lost if the
    # lamp's uneven light swells the noise estimate (no high-pass).
    return board(), lit_by(marks.word(board(), FAINT_INK_DEPTH), *LAMP_GAIN)


def new_faint_word_as_the_lights_come_up(board: Frames, marks: SimpleNamespace) -> Pair:
    # Lost if the lit frame is scaled down to the dark one instead of the other way.
    dark = lit_by(board(), LIGHTS_DOWN_GAIN, LIGHTS_DOWN_GAIN)
    return dark, marks.word(board(), FAINT_INK_DEPTH)


def noise_and_a_one_pixel_shift(board: Frames, marks: SimpleNamespace) -> Pair:
    # Enough ink that the shift alone would count, without ALIGN_TOLERANCE_PX.
    after = marks.hello(board())
    shift = np.float32([[1, 0, 1], [0, 1, 1]])
    shifted = cv2.warpAffine(after, shift, after.shape[1::-1], borderMode=cv2.BORDER_REPLICATE)
    return marks.hello(board()), shifted


def dim_room_smudges_flickering(board: Frames, marks: SimpleNamespace) -> Pair:
    dim = dim_room()
    return dim(), dim()


def board_frame_in_the_border_strip(board: Frames, marks: SimpleNamespace) -> Pair:
    # What every "change" from a still board was in the real logs.
    return board(), marks.board_edge(board())


def glare_spot_swelling_in_a_dim_room(board: Frames, marks: SimpleNamespace) -> Pair:
    # Its halo only looks darker than a neighbourhood mean the spot drags up.
    dim = dim_room()
    before_px, after_px = GLARE_CORE_PX
    return marks.glare(dim(), before_px), marks.glare(dim(), after_px)


def new_word_beside_a_swelling_glare_spot(board: Frames, marks: SimpleNamespace) -> Pair:
    dim = dim_room()
    before_px, after_px = GLARE_CORE_PX
    return marks.glare(dim(), before_px), marks.glare(marks.word(dim()), after_px)


def new_filled_box(board: Frames, marks: SimpleNamespace) -> Pair:
    after = board()
    cv2.rectangle(after, *FILLED_BOX, (FILLED_BOX_GREY,) * 3, -1)
    return board(), after


def test_new_ink_is_a_change_with_its_bbox(
    board_image: Frames, marks: SimpleNamespace, ink_region: tuple[int, int, int, int]
) -> None:
    change = ink_change(board_image(), marks.hello(board_image()))

    assert change.ratio >= INK_CHANGE_RATIO
    assert change.bbox is not None
    x, y, w, h = change.bbox
    x0, y0, x1, y1 = ink_region
    assert x0 <= x and y0 <= y and x + w <= x1 and y + h <= y1


@pytest.mark.parametrize(
    ("make_pair", "is_change"),
    [
        (new_small_word_in_a_dim_room, True),
        (new_faint_word_as_the_lights_go_down_to_a_lamp, True),
        (new_faint_word_as_the_lights_come_up, True),
        (new_word_beside_a_swelling_glare_spot, True),
        (new_filled_box, True),
        (noise_and_a_one_pixel_shift, False),
        (dim_room_smudges_flickering, False),
        (board_frame_in_the_border_strip, False),
        (glare_spot_swelling_in_a_dim_room, False),
    ],
)
def test_only_real_strokes_count_as_an_ink_change(
    make_pair: Callable[[Frames, SimpleNamespace], Pair],
    is_change: bool,
    board_image: Frames,
    marks: SimpleNamespace,
) -> None:
    before, after = make_pair(board_image, marks)

    assert (ink_change(before, after).ratio >= INK_CHANGE_RATIO) == is_change
