"""Tests for ChangeWatcher on a fake board: new ink fires once; a passer-by, Claude's own
projection, the daemon's own flashes, a dark room and the idle view's scrolling news
ticker (in its masked band) never cost a flash; captures wait
min_interval_s unless the change is large (and Claude's answer or the flickering edge
of the view aren't)."""

import math
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from whiteboard.camera import BLANK_MODE, Calibration, CaptureRig, ChangeWatcher
from whiteboard.config import WatcherSettings

pytestmark = pytest.mark.asyncio

PERSON_BOX = ((600, 50), (900, 720))
PROJECTED_BOX = ((950, 100), (1200, 250))
# Top-left corners of the bright calibration markers a marker check flashes.
MARKER_CORNERS = [(x, y) for x in (100, 540, 980) for y in (100, 420)]
MARKER_SIDE_PX = 200
# Where Claude's projected answer goes: bright text lines, like a real reply.
ANSWER_LINE_YS = (450, 520, 590)
INK_GREY = (50, 50, 50)
# The camera's exposure: a lights-off room, and the overshoot right after a blank.
DARK_ROOM_GAIN = 0.1
OVERSHOOT_GAIN = 1.6
# What's left of the overshoot once settle_s is over; only brightness matching hides it.
EXPOSURE_TAIL_GAIN = 1.3
MIN_INTERVAL_S = WatcherSettings().min_interval_s
# The idle view's news ticker: bright headlines along the bottom of the 1280x720 view
# (big and bold, as the real one reads in a dim room), and its band as the daemon's
# BoardController.motion_masks would give it (y 612 to 720).
TICKER_Y = 690
TICKER_BAND = (0.0, 0.85, 1.0, 0.15)
TICKER_PX_PER_STEP = 75

Report = tuple[Path, tuple[int, int, int, int]]


class FakeBoard:
    """A camera and board page in one: frames show ink, plus a person, the
    projection and the calibration markers when present, at the camera's current
    exposure. The projection disappears while the page is blank. `page_changed_s`
    is what the daemon's BoardController would report."""

    def __init__(self, board_image: Callable[[], np.ndarray]) -> None:
        self._board_image = board_image
        self.ink_layer: Callable[[np.ndarray], np.ndarray] = lambda image: image
        self.has_person = False
        self.has_projection = False
        self.has_markers = False
        self.has_answer = False
        self.ticker_x: int | None = None
        self.gain = 1.0
        self.mode = "normal"
        self.modes: list[str] = []
        self.page_changed_s = -math.inf

    def _frame(self) -> np.ndarray:
        frame = self.ink_layer(self._board_image())
        if self.has_projection and self.mode != BLANK_MODE:
            cv2.rectangle(frame, *PROJECTED_BOX, (255, 255, 0), 6)
        if self.has_answer and self.mode != BLANK_MODE:
            for y in ANSWER_LINE_YS:
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frame, "Projected answer", (300, y), font, 1.5, (255, 255, 255), 3)
        if self.ticker_x is not None and self.mode != BLANK_MODE:
            text = "Rates held | Storm hits coast | Vote tonight | " * 10
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, text, (self.ticker_x, TICKER_Y), font, 2.5, (255, 255, 255), 7)
        if self.has_person:
            cv2.rectangle(frame, *PERSON_BOX, (40, 40, 40), -1)
        if self.has_markers:
            for x, y in MARKER_CORNERS:
                corner = (x + MARKER_SIDE_PX, y + MARKER_SIDE_PX)
                cv2.rectangle(frame, (x, y), corner, (255, 255, 255), -1)
        return cv2.convertScaleAbs(frame, alpha=self.gain)

    def latest(self) -> np.ndarray:
        return self._frame()

    def read_fresh(self) -> np.ndarray:
        return self._frame()

    async def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.modes.append(mode)

    @property
    def captures(self) -> int:
        return self.modes.count(BLANK_MODE)


def make_watcher(
    board: FakeBoard,
    tmp_path: Path,
    reports: list[Report],
    masks: tuple = (),
    calibration: Calibration | None = None,
) -> ChangeWatcher:
    rig = CaptureRig(
        board,
        board.set_mode,
        tmp_path,
        0,
        5,
        page_changed_s=lambda: board.page_changed_s,
        motion_masks=lambda: masks,
        calibration=calibration,
    )

    async def on_board_changed(path: Path, bbox: tuple[int, int, int, int]) -> None:
        reports.append((path, bbox))

    return ChangeWatcher(rig, WatcherSettings(), on_board_changed)


async def run_steps(watcher: ChangeWatcher, times: range) -> None:
    for now_s in times:
        await watcher.step(now_s)


async def run_scenario(
    board: FakeBoard, tmp_path: Path, add_ink: Callable[[np.ndarray], np.ndarray] | None
) -> list[Report]:
    """Baseline, then someone walks up (maybe draws), leaves, and the board goes still."""
    reports: list[Report] = []
    watcher = make_watcher(board, tmp_path, reports)
    await watcher.step(0)  # baseline capture
    await watcher.step(5)  # the first sample once settled: the motion reference
    board.has_person = True
    await watcher.step(40)
    if add_ink is not None:
        board.ink_layer = add_ink
    board.has_projection = True  # Claude draws something meanwhile
    await watcher.step(41)
    board.has_person = False
    await run_steps(watcher, range(42, 50))
    return reports


async def test_new_ink_fires_once_with_its_bbox(
    board_image: Callable[[], np.ndarray],
    marks: SimpleNamespace,
    ink_region: tuple[int, int, int, int],
    tmp_path: Path,
) -> None:
    reports = await run_scenario(FakeBoard(board_image), tmp_path, marks.hello)

    assert len(reports) == 1
    path, (x, y, w, h) = reports[0]
    assert path.exists()
    x0, y0, x1, y1 = ink_region
    assert x0 <= x and y0 <= y and x + w <= x1 and y + h <= y1


async def test_passer_by_and_projection_without_ink_do_not_fire(
    board_image: Callable[[], np.ndarray], tmp_path: Path
) -> None:
    board = FakeBoard(board_image)

    reports = await run_scenario(board, tmp_path, add_ink=None)

    assert reports == []
    # A second clean capture did happen after the motion; it just found no new ink.
    assert board.captures == 2


async def test_the_daemons_own_flash_never_schedules_a_capture(
    board_image: Callable[[], np.ndarray], tmp_path: Path
) -> None:
    board = FakeBoard(board_image)
    board.has_projection = True
    watcher = make_watcher(board, tmp_path, [])
    await run_steps(watcher, range(0, 6))  # baseline, then settled

    # A marker check flashes the markers. The page goes back to normal, but the camera
    # lags a moment behind it, then its exposure swings back slowly.
    board.has_markers, board.page_changed_s = True, math.inf
    await watcher.step(40)
    board.page_changed_s = 40.3
    await watcher.step(41)  # the camera still shows the markers
    board.has_markers, board.gain = False, OVERSHOOT_GAIN
    await run_steps(watcher, range(42, 44))
    board.gain = EXPOSURE_TAIL_GAIN
    await run_steps(watcher, range(44, 46))
    board.gain = 1.0
    await run_steps(watcher, range(46, 120))

    assert board.captures == 1  # only the baseline


async def test_a_dark_room_is_never_blanked_until_the_light_comes_back(
    board_image: Callable[[], np.ndarray], tmp_path: Path
) -> None:
    board = FakeBoard(board_image)
    board.gain = DARK_ROOM_GAIN
    watcher = make_watcher(board, tmp_path, [])

    await run_steps(watcher, range(0, 60))
    assert board.captures == 0  # not even the baseline

    board.gain = 1.0
    await run_steps(watcher, range(60, 62))
    assert board.captures == 1


def whole_lines(image: np.ndarray) -> np.ndarray:
    inked = image.copy()
    for y in (150, 300, 450):
        cv2.putText(inked, "HELLO", (150, y), cv2.FONT_HERSHEY_SIMPLEX, 2, INK_GREY, 4)
    return inked


def write_a_word(board: FakeBoard, marks: SimpleNamespace) -> None:
    board.ink_layer = marks.word


def write_whole_lines(board: FakeBoard, marks: SimpleNamespace) -> None:
    board.ink_layer = whole_lines


def project_an_answer(board: FakeBoard, marks: SimpleNamespace) -> None:
    # Bright text in the live view, but the daemon's own page change, not new ink.
    board.has_answer, board.page_changed_s = True, 7.0


def flicker_the_edge(board: FakeBoard, marks: SimpleNamespace) -> None:
    board.ink_layer = marks.board_edge


@pytest.mark.parametrize(
    ("change", "capture_s"),
    [
        (write_a_word, MIN_INTERVAL_S),
        (write_whole_lines, 11),
        (project_an_answer, MIN_INTERVAL_S),
        (flicker_the_edge, MIN_INTERVAL_S),
    ],
)
async def test_captures_wait_min_interval_unless_the_change_is_large(
    change: Callable[[FakeBoard, SimpleNamespace], None],
    capture_s: float,
    board_image: Callable[[], np.ndarray],
    marks: SimpleNamespace,
    tmp_path: Path,
) -> None:
    board = FakeBoard(board_image)
    watcher = make_watcher(board, tmp_path, [])
    await run_steps(watcher, range(0, 6))  # baseline, then settled
    board.has_person = True
    await watcher.step(6)  # motion: a capture is due once the board is still
    change(board, marks)
    board.has_person = False
    await watcher.step(7)

    for now_s in range(8, 40):
        await watcher.step(now_s)
        if board.captures == 2:
            break
    assert now_s == capture_s


@pytest.mark.parametrize(("masks", "is_masked"), [((TICKER_BAND,), True), ((), False)])
async def test_a_scrolling_ticker_in_its_masked_band_is_not_motion(
    masks: tuple,
    is_masked: bool,
    board_image: Callable[[], np.ndarray],
    tmp_path: Path,
) -> None:
    board = FakeBoard(board_image)
    board.ticker_x = 0
    # Masks only apply to a rectified view: an identity calibration gives one.
    identity = Calibration(np.eye(3), (1280, 720), (1280, 720), 0.3, 6, "")
    watcher = make_watcher(board, tmp_path, [], masks, identity)

    async def scroll(times: range) -> None:
        for now_s in times:
            board.ticker_x -= TICKER_PX_PER_STEP
            await watcher.step(now_s)

    await run_steps(watcher, range(0, 6))  # baseline, then settled
    await scroll(range(6, 60))
    # Masked, the ticker is never motion (the drift monitor sees the board idle too).
    # Unmasked, it's motion every second.
    assert (watcher.last_motion_s == -math.inf) is is_masked
    assert board.captures == 1

    # Someone at the board outside the band: masked, the watcher sees them and takes a
    # capture once they've gone; unmasked, the ticker never lets the board look still.
    board.has_person = True
    await watcher.step(60)
    board.has_person = False
    await scroll(range(61, 100))
    assert board.captures == (2 if is_masked else 1)
