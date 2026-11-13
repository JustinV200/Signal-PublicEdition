"""Opening webcams through OpenCV: backend choice and probing.

`Camera` (camera.py) opens its device here. `open_capture` tries the configured
capture API first, then the other Windows one, and keeps whichever delivers frames
at the requested resolution. `list_cameras` backs the `whiteboard cameras` command.
"""

import logging
import os
from dataclasses import dataclass

# MSMF's hardware transforms make opening a 4K webcam take 10+ seconds. OpenCV
# reads this when the first MSMF capture opens, so it must be set before that.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2  # noqa: E402

logger = logging.getLogger(__name__)

BACKENDS: dict[str, int] = {"msmf": cv2.CAP_MSMF, "dshow": cv2.CAP_DSHOW, "any": cv2.CAP_ANY}
# Tried after the configured backend when it can't deliver the requested size.
FALLBACK_ORDER: tuple[str, ...] = ("msmf", "dshow")
# Webcams often return a few empty reads while they start streaming.
WARMUP_READS = 10
# Indexes `list_cameras` probes. Windows rarely numbers webcams past 4.
PROBE_INDEXES = range(5)


class CameraError(RuntimeError):
    """The webcam could not be opened or stopped delivering frames."""


@dataclass
class OpenedCapture:
    """An open `cv2.VideoCapture` and what it actually delivers."""

    capture: cv2.VideoCapture
    backend: str
    width: int
    height: int
    fps: float


def _try_open(index: int, backend: str, width: int, height: int) -> OpenedCapture | None:
    """Open one device on one backend and read a frame. Returns None if it can't."""
    capture = cv2.VideoCapture(index, BACKENDS[backend])
    if not capture.isOpened():
        capture.release()
        return None
    # MJPG is what lets USB webcams stream 1080p at full frame rate; raw YUY2
    # at that size usually drops to about 5 fps.
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    for _ in range(WARMUP_READS):
        is_ok, frame = capture.read()
        if is_ok and frame is not None:
            frame_height, frame_width = frame.shape[:2]
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            return OpenedCapture(capture, backend, frame_width, frame_height, fps)
    capture.release()
    return None


def _backend_order(preferred: str) -> list[str]:
    """The configured backend first, then the Windows fallbacks it isn't."""
    if preferred not in BACKENDS:
        raise CameraError(f"unknown camera backend {preferred!r}; use one of {sorted(BACKENDS)}")
    return [preferred, *(name for name in FALLBACK_ORDER if name != preferred)]


def open_capture(index: int, width: int, height: int, preferred: str) -> OpenedCapture:
    """Open camera `index`, preferring a backend that delivers exactly width x height.

    Args:
        index: OpenCV camera index.
        width: Requested frame width in pixels.
        height: Requested frame height in pixels.
        preferred: Backend name to try first ("msmf", "dshow" or "any").

    Returns:
        The open capture. If no backend gives the requested size, the first backend
        that opened at all is reopened and used, with a warning.

    Raises:
        CameraError: If no backend can open the camera or read a frame from it.
    """
    first_working: str | None = None
    for backend in _backend_order(preferred):
        opened = _try_open(index, backend, width, height)
        if opened is None:
            continue
        if (opened.width, opened.height) == (width, height):
            return opened
        logger.info("camera %d via %s gives %dx%d", index, backend, opened.width, opened.height)
        opened.capture.release()
        first_working = first_working or backend
    if first_working is not None:
        opened = _try_open(index, first_working, width, height)
        if opened is not None:
            logger.warning(
                "camera %d can't do %dx%d; using %s at %dx%d",
                index,
                width,
                height,
                first_working,
                opened.width,
                opened.height,
            )
            return opened
    raise CameraError(f"camera {index} would not open or deliver frames (tried {preferred})")


@dataclass(frozen=True)
class CameraInfo:
    """One camera index that opened on one backend, and the size it delivered."""

    index: int
    backend: str
    width: int
    height: int
    fps: float


def list_cameras(width: int = 1920, height: int = 1080) -> list[CameraInfo]:
    """Probe camera indexes 0-4 on MSMF and DirectShow at the requested size.

    Opens and closes each device, so it takes a few seconds and must not run while
    the daemon holds the camera. OpenCV can't read device names, so entries are
    identified by index and backend only.
    """
    # Missing indexes are expected here; OpenCV would print a warning for each.
    previous_level = cv2.utils.logging.getLogLevel()
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    try:
        return [info for index in PROBE_INDEXES for info in _probe(index, width, height)]
    finally:
        cv2.utils.logging.setLogLevel(previous_level)


def _probe(index: int, width: int, height: int) -> list[CameraInfo]:
    """Each Windows backend that opens camera `index`, with the size it delivered."""
    found: list[CameraInfo] = []
    for backend in FALLBACK_ORDER:
        opened = _try_open(index, backend, width, height)
        if opened is None:
            continue
        opened.capture.release()
        found.append(CameraInfo(index, backend, opened.width, opened.height, opened.fps))
    return found
