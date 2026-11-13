"""The webcam as a live frame source: a background thread keeps the newest frame.

The daemon opens one `Camera` and shares it. The change watcher samples
`latest()` once a second. Clean captures and calibration call `read_fresh()`,
which waits for a frame exposed after the call, so a frame from before the page
went black (or before the pattern appeared) is never used. If the webcam stops
delivering (unplugged, taken by another app), the thread reopens it with backoff
and `latest()` returns None meanwhile, so nothing works on a stale frame.
"""

import logging
import threading
import time
from types import TracebackType

import numpy as np

from whiteboard.camera.device import CameraError, OpenedCapture, open_capture
from whiteboard.config import CameraSettings

logger = logging.getLogger(__name__)

# The first frame after a call may have been mid-exposure when the scene
# changed, so read_fresh waits for the one after it.
FRESH_FRAME_GAP = 2
FRESH_TIMEOUT_S = 3.0
# A frame older than this means the camera has stopped delivering.
STALE_FRAME_S = 2.0
# Pause after a failed read so an unplugged camera doesn't spin the thread.
READ_RETRY_S = 0.2
# Consecutive failed reads (about 1 s) before the device is closed and reopened.
REOPEN_AFTER_FAILURES = 5
REOPEN_FIRST_DELAY_S = 1.0
REOPEN_MAX_DELAY_S = 30.0
# How long close() waits for a blocked read before giving up on the thread.
JOIN_TIMEOUT_S = 5.0


class Camera:
    """A webcam with a grab thread. Use as a context manager, or call open()/close().

    Usage:
        with Camera(settings.camera) as camera:
            frame = camera.read_fresh()
    """

    def __init__(self, settings: CameraSettings) -> None:
        """Remember which camera to open; nothing is opened until open().

        Args:
            settings: Index, resolution and preferred backend ([camera] in config).
        """
        self._settings = settings
        self._opened: OpenedCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._new_frame = threading.Condition()
        self._frame: np.ndarray | None = None
        self._frame_time_s = 0.0
        self._frame_count = 0

    @property
    def info(self) -> OpenedCapture | None:
        """The open capture's backend, size and fps, or None while closed."""
        return self._opened

    def open(self) -> None:
        """Open the device and start the grab thread.

        Raises:
            CameraError: If the camera can't be opened (see device.open_capture).
        """
        if self._opened is not None:
            return
        self._opened = self._open_device()
        self._stop.clear()
        self._thread = threading.Thread(target=self._grab_loop, name="camera-grab", daemon=True)
        self._thread.start()

    def close(self) -> None:
        """Stop the grab thread and release the device. Wakes read_fresh waiters. Safe twice."""
        if self._opened is None:
            return
        self._stop.set()
        with self._new_frame:
            self._new_frame.notify_all()
        if self._thread is not None:
            self._thread.join(JOIN_TIMEOUT_S)
        if self._thread is not None and self._thread.is_alive():
            # Releasing under a read that's still in flight can crash OpenCV, so
            # leave the device to be freed at process exit instead.
            logger.error("camera grab thread did not stop; device stays open")
        else:
            self._opened.capture.release()
        self._opened = None
        self._thread = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def latest(self) -> np.ndarray | None:
        """The newest BGR frame, or None if there's none from the last STALE_FRAME_S.

        Never blocks.
        """
        with self._new_frame:
            if time.monotonic() - self._frame_time_s > STALE_FRAME_S:
                return None
            return self._frame

    def read_fresh(self, timeout_s: float = FRESH_TIMEOUT_S) -> np.ndarray:
        """Block until a frame exposed after this call arrives, and return it (BGR).

        Raises:
            CameraError: If the camera is closed or no fresh frame arrives in time.
        """
        with self._new_frame:
            target = self._frame_count + FRESH_FRAME_GAP
            has_frame = self._new_frame.wait_for(
                lambda: self._frame_count >= target or self._stop.is_set(), timeout_s
            )
            if self._stop.is_set() or self._opened is None:
                raise CameraError("camera is closed")
            if not has_frame or self._frame is None:
                raise CameraError(f"no fresh camera frame within {timeout_s:.1f} s")
            return self._frame

    def _open_device(self) -> OpenedCapture:
        """Open the configured device and log what it delivers. Raises CameraError."""
        settings = self._settings
        opened = open_capture(settings.index, settings.width, settings.height, settings.backend)
        logger.info(
            "camera %d open via %s at %dx%d, %.0f fps",
            settings.index,
            opened.backend,
            opened.width,
            opened.height,
            opened.fps,
        )
        return opened

    def _grab_loop(self) -> None:
        """Thread body: read and publish frames until stopped, reopening a dead device."""
        failures = 0
        while not self._stop.is_set():
            assert self._opened is not None
            is_ok, frame = self._opened.capture.read()
            if is_ok and frame is not None:
                failures = 0
                self._publish(frame)
                continue
            failures += 1
            if failures < REOPEN_AFTER_FAILURES:
                self._stop.wait(READ_RETRY_S)
                continue
            logger.warning("camera stopped delivering frames; reopening it")
            self._reopen_with_backoff()
            failures = 0

    def _reopen_with_backoff(self) -> None:
        """Release the device, then retry opening it 1, 2, 4 ... 30 s apart until it works.

        Returns early when the camera is closed.
        """
        assert self._opened is not None
        self._opened.capture.release()
        delay_s = REOPEN_FIRST_DELAY_S
        while not self._stop.wait(delay_s):
            try:
                self._opened = self._open_device()
                return
            except CameraError as error:
                delay_s = min(delay_s * 2, REOPEN_MAX_DELAY_S)
                logger.warning("camera reopen failed (%s); retrying in %.0f s", error, delay_s)

    def _publish(self, frame: np.ndarray) -> None:
        """Make `frame` the newest one and wake read_fresh waiters."""
        with self._new_frame:
            self._frame = frame
            self._frame_time_s = time.monotonic()
            self._frame_count += 1
            self._new_frame.notify_all()
