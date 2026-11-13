"""Ink extraction on a synthetic board: dark strokes (and a filled box) on white -> bright
strokes on transparent, and the projector's glare spot isn't ink."""

from collections.abc import Callable

import cv2
import numpy as np

from whiteboard.saves import extract_ink

# OpenCV colours are BGR.
WHITE_BOARD = (235, 235, 235)
BLACK_INK = (30, 30, 30)
BLUE_INK = (170, 80, 30)
# A dim room, where the glare spot's halo is strongest against the board.
DIM_BOARD = (60, 60, 60)
GLARE_CENTER = (150, 100)
GLARE_CORE_PX = 12
# A stroke this far right of the glare's centre, through its halo.
STROKE_OFFSET_PX = 20
STROKE_WIDTH_PX = 3


def hue(bgr: np.ndarray) -> int:
    return int(cv2.cvtColor(bgr.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV)[0, 0, 0])


def test_strokes_become_bright_on_transparent_and_keep_their_hue() -> None:
    photo = np.full((200, 300, 3), WHITE_BOARD, np.uint8)
    cv2.line(photo, (20, 50), (280, 50), BLACK_INK, 5)
    cv2.line(photo, (20, 150), (280, 150), BLUE_INK, 5)
    cv2.rectangle(photo, (200, 70), (259, 129), BLACK_INK, -1)  # a filled 60x60 box

    ink = extract_ink(photo)

    assert ink.shape == (200, 300, 4)
    assert ink[100, 150, 3] == 0  # bare board: transparent
    black_stroke, blue_stroke = ink[50, 150], ink[150, 150]
    assert black_stroke.tolist() == [255, 255, 255, 255]  # black ink turns white
    assert blue_stroke[3] == 255 and max(blue_stroke[:3]) == 255
    assert abs(hue(blue_stroke[:3]) - hue(np.array(BLUE_INK))) <= 2
    assert min(blue_stroke[:3]) < 50  # saturated, not washed out to white
    assert ink[100, 203, 3] == 255  # the filled box is ink too (its rim, like any wide mark)


def test_glare_spot_is_not_ink_but_a_stroke_through_its_halo_is(
    paint_glare: Callable[[np.ndarray, tuple[int, int], int], np.ndarray],
) -> None:
    photo = paint_glare(np.full((200, 300, 3), DIM_BOARD, np.uint8), GLARE_CENTER, GLARE_CORE_PX)
    stroke_x = GLARE_CENTER[0] + STROKE_OFFSET_PX
    cv2.line(photo, (stroke_x, 40), (stroke_x, 160), BLACK_INK, STROKE_WIDTH_PX)

    is_ink = extract_ink(photo)[..., 3] > 0

    assert is_ink[GLARE_CENTER[1], stroke_x]  # the stroke is kept, right beside the spot
    ink_columns = np.nonzero(is_ink)[1]
    assert np.all(np.abs(ink_columns - stroke_x) <= STROKE_WIDTH_PX)  # nothing but the stroke
