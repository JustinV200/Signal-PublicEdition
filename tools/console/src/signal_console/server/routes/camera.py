"""GET /api/camera/stream: the whiteboard webcam's live MJPEG stream, proxied for System's camera.

The whiteboard daemon serves the stream only with its X-Signal-Token header.
The console server adds that header itself, so the page never sees the
token: the page sends its own X-Console-Token (checked by the guard like
every /api route), and gets back only the multipart body under headers the
console writes. The daemon's limits come back as plain words: 429 when its
2 viewers are taken, 503 when the camera is off or has no frame. Closing the
page's request ends the upstream one, which frees the daemon's slot.
This is a read, like the console's other status reads: nothing is asked of
the orchestrator and the camera is never moved or switched.
"""

import logging

import aiohttp
from aiohttp import web

from signal_console.server.services import SERVICES_KEY
from signal_console.status import find_whiteboard

STREAM_PATH = "/api/camera/stream"
MJPEG_TYPE = "multipart/x-mixed-replace"
CONNECT_TIMEOUT_S = 2.0
# The daemon sends a frame about every 0.2 s; this long without one means it's stuck.
READ_TIMEOUT_S = 10.0

WHITEBOARD_OFF = "The whiteboard is off, so there's no camera to show."
NOT_ANSWERING = "The whiteboard isn't answering."
TOO_MANY_VIEWERS = (
    "The camera already has 2 viewers, the whiteboard's limit. Close one (or wait a few "
    "seconds for a closed one to drop), then try again."
)
NO_PICTURE = "The camera is off or has no live picture right now (unplugged or reconnecting?)."
REFUSED = "The whiteboard refused the console's request (did the daemon restart?)."
UNEXPECTED = "The whiteboard sent something that isn't a camera stream."

log = logging.getLogger(__name__)


def add_camera_route(app: web.Application) -> None:
    """Register GET /api/camera/stream."""
    app.router.add_get(STREAM_PATH, camera_stream)


async def camera_stream(request: web.Request) -> web.StreamResponse:
    """Pass the daemon's camera stream through until the page or the daemon goes."""
    services = request.app[SERVICES_KEY]
    target = find_whiteboard(services.whiteboard_dir)
    if target is None:
        return _error(503, WHITEBOARD_OFF)
    timeout = aiohttp.ClientTimeout(sock_connect=CONNECT_TIMEOUT_S, sock_read=READ_TIMEOUT_S)
    try:
        # No redirects: the whiteboard token must only ever go to the daemon's own address.
        upstream = await services.session.get(
            f"{target.base_url}{STREAM_PATH}",
            headers=target.headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except (aiohttp.ClientError, TimeoutError) as error:
        log.info("camera stream: whiteboard not answering: %s", error)
        return _error(503, NOT_ANSWERING)
    try:
        content_type = upstream.headers.get("Content-Type", "")
        refusal = _refusal(upstream.status, content_type)
        if refusal is not None:
            return refusal
        return await _relay(request, upstream, content_type)
    finally:
        upstream.close()


def _refusal(status: int, content_type: str) -> web.Response | None:
    """The page's answer when the daemon didn't send a stream, else None."""
    if status == 429:
        return _error(429, TOO_MANY_VIEWERS)
    if status == 503:
        return _error(503, NO_PICTURE)
    if status in (401, 403):
        return _error(502, REFUSED)
    if status != 200 or not content_type.startswith(MJPEG_TYPE):
        return _error(502, UNEXPECTED)
    return None


async def _relay(
    request: web.Request, upstream: aiohttp.ClientResponse, content_type: str
) -> web.StreamResponse:
    # Only the content type (with its boundary) crosses over; every other header is ours.
    response = web.StreamResponse(headers={"Content-Type": content_type})
    await response.prepare(request)
    try:
        async for chunk in upstream.content.iter_any():
            await response.write(chunk)
    except ConnectionResetError:
        pass  # The page closed the camera view; upstream.close() frees the daemon's slot.
    except (aiohttp.ClientError, TimeoutError) as error:
        log.info("camera stream ended: %s", error)
    return response


def _error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)
