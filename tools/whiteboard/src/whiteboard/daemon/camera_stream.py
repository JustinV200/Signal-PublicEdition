"""GET /api/camera/stream: the raw webcam view as a low-rate MJPEG stream, for aiming the camera.

It never opens the camera itself: it re-encodes the newest frame the daemon's one
`Camera` grab thread already keeps (`Camera.latest`), so the watcher, looks and
calibration are untouched. It never changes the page either (no blank, no
markers) and never rectifies: this is what the lens sees. Like every /api/ route
it sits behind the request guard, so it needs the X-Signal-Token header. A future
console page will proxy it rather than hold the token in a browser.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable

import cv2
import numpy as np
from aiohttp import web

logger = logging.getLogger(__name__)

STREAM_PATH = "/api/camera/stream"
# About 5 fps is enough to aim by and keeps the encode cost tiny.
FRAME_INTERVAL_S = 0.2
JPEG_QUALITY = 70
# Frames wider than this are scaled down before encoding (1080p becomes 960x540).
MAX_WIDTH_PX = 960
# Each stream costs an encode per frame, so a stray tab can't pile them up.
MAX_STREAMS = 2
BOUNDARY = "frame"
# A viewer that hasn't taken a frame in this long counts as gone, so a stalled one
# can't keep its slot or hold up the daemon's shutdown.
WRITE_TIMEOUT_S = 5.0

NO_CAMERA = "the camera isn't available in this daemon"
NO_FRAME = "the camera has no live frame right now (unplugged or reconnecting?)"
TOO_MANY = f"at most {MAX_STREAMS} camera streams at once; close one first"

LatestFrame = Callable[[], np.ndarray | None]


class CameraStream:
    """Serves the MJPEG stream from a latest-frame source, with a cap on open streams."""

    def __init__(self, latest_frame: LatestFrame | None, stop: asyncio.Event) -> None:
        """Args:
        latest_frame: Returns the newest BGR frame or None (normally `Camera.latest`);
            None when the daemon has no camera, so every request gets a 503.
        stop: Set when the daemon shuts down; open streams end within one frame.
        """
        self._latest_frame = latest_frame
        self._stop = stop
        self._open_streams = 0

    async def handle(self, request: web.Request) -> web.StreamResponse:
        """Answer one stream request: 503 without a camera or frame, 429 over the cap."""
        latest_frame = self._latest_frame
        if latest_frame is None:
            return _error(NO_CAMERA, 503)
        if self._open_streams >= MAX_STREAMS:
            return _error(TOO_MANY, 429)
        if latest_frame() is None:
            return _error(NO_FRAME, 503)
        # One event loop, so a plain counter needs no lock.
        self._open_streams += 1
        try:
            return await self._stream(request, latest_frame)
        finally:
            self._open_streams -= 1

    async def _stream(self, request: web.Request, latest_frame: LatestFrame) -> web.StreamResponse:
        """Write frames until the client goes, the camera stops, or the daemon stops."""
        response = web.StreamResponse(
            headers={
                "Content-Type": f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                "Cache-Control": "no-store",
            }
        )
        await response.prepare(request)
        while not self._stop.is_set():
            frame = latest_frame()
            if frame is None:
                logger.info("camera stream ended: no live frame")
                break
            part = mjpeg_part(await asyncio.to_thread(encode_jpeg, frame))
            try:
                await asyncio.wait_for(response.write(part), WRITE_TIMEOUT_S)
            except ConnectionResetError:
                # The viewer closed its window or tab (aiohttp's reset error subclasses this).
                break
            except TimeoutError:
                # The viewer stopped reading: drop its socket now and free the slot.
                if request.transport is not None:
                    request.transport.close()
                break
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), FRAME_INTERVAL_S)
        return response


def encode_jpeg(frame: np.ndarray) -> bytes:
    """Scale a BGR frame down to MAX_WIDTH_PX (if wider) and JPEG-encode it.

    Raises:
        ValueError: OpenCV couldn't encode the frame.
    """
    height, width = frame.shape[:2]
    if width > MAX_WIDTH_PX:
        size = (MAX_WIDTH_PX, round(height * MAX_WIDTH_PX / width))
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    is_ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not is_ok:
        raise ValueError("couldn't JPEG-encode the camera frame")
    return encoded.tobytes()


def mjpeg_part(jpeg: bytes) -> bytes:
    """One multipart part: boundary, headers (with Content-Length), the JPEG, CRLF."""
    head = (
        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n"
    ).encode("ascii")
    return head + jpeg + b"\r\n"


def add_camera_stream_route(
    app: web.Application, latest_frame: LatestFrame | None, stop: asyncio.Event
) -> None:
    """Register GET /api/camera/stream on the daemon's app (before it starts).

    Args:
        app: The daemon's app; its request guard already covers /api/.
        latest_frame: `Camera.latest`, or None when the camera didn't open.
        stop: The daemon's stop event.
    """
    app.router.add_get(STREAM_PATH, CameraStream(latest_frame, stop).handle)


def _error(message: str, status: int) -> web.Response:
    """An error in the API's {ok, error} shape."""
    return web.json_response({"ok": False, "error": message}, status=status)
