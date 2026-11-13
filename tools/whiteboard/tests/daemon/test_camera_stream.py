"""GET /api/camera/stream behind the real request guard, read with the real client.

The stream must need the token, re-encode the shared latest frame without ever
opening a camera, end when the daemon stops, and free its slot when a viewer leaves.
"""

import asyncio
import socket

import cv2
import numpy as np
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from whiteboard.daemon import camera_stream
from whiteboard.daemon.camera_stream import MAX_STREAMS, MAX_WIDTH_PX, add_camera_stream_route
from whiteboard.daemon.request_guard import build_request_guard
from whiteboard.daemon_client import DaemonApi, DaemonApiError, iter_jpeg_parts

pytestmark = pytest.mark.asyncio

TOKEN = "s3cret"
# A 1080p frame of one grey, so the decoded JPEG can be checked against it.
FRAME_GREY = 180
FAKE_FRAME = np.full((1080, 1920, 3), FRAME_GREY, np.uint8)
# The server notices a gone viewer at its next write, one frame interval later.
SLOT_FREED_WITHIN_S = 3.0


async def start_server(latest_frame, stop: asyncio.Event) -> TestServer:
    """An app with only the guard and the stream route, on a free loopback port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = web.Application(middlewares=[build_request_guard(TOKEN, port)])
    add_camera_stream_route(app, latest_frame, stop)
    server = TestServer(app, host="127.0.0.1", port=port)
    await server.start_server()
    return server


def api_for(server: TestServer, token: str = TOKEN) -> DaemonApi:
    """The real blocking client, pointed at the test server."""
    return DaemonApi(f"http://127.0.0.1:{server.port}", token)


@pytest.mark.parametrize(
    ("token", "latest_frame", "status"),
    [
        ("", lambda: FAKE_FRAME, "403"),
        ("nope", lambda: FAKE_FRAME, "403"),
        (TOKEN, None, "503"),  # the daemon has no camera
        (TOKEN, lambda: None, "503"),  # the camera has no live frame
    ],
)
async def test_stream_refuses_without_token_or_live_camera(token, latest_frame, status) -> None:
    stop = asyncio.Event()
    server = await start_server(latest_frame, stop)
    try:
        with pytest.raises(DaemonApiError, match=status):
            await asyncio.to_thread(api_for(server, token).open_camera_stream)
    finally:
        stop.set()
        await server.close()


async def test_stream_sends_the_shared_frame_and_ends_when_the_daemon_stops(monkeypatch) -> None:
    opened_devices = []
    monkeypatch.setattr(camera_stream.cv2, "VideoCapture", lambda *a: opened_devices.append(a))
    stop = asyncio.Event()
    server = await start_server(lambda: FAKE_FRAME, stop)
    try:
        stream = await asyncio.to_thread(api_for(server).open_camera_stream)
        parts = iter_jpeg_parts(stream)
        jpegs = [await asyncio.to_thread(next, parts) for _ in range(2)]
        stop.set()
        rest = await asyncio.to_thread(list, parts)
        stream.close()
    finally:
        await server.close()
    frame = cv2.imdecode(np.frombuffer(jpegs[1], np.uint8), cv2.IMREAD_COLOR)
    assert frame.shape == (540, MAX_WIDTH_PX, 3)
    assert abs(int(frame.mean()) - FRAME_GREY) <= 2
    assert len(rest) <= 1  # at most the frame already in flight
    assert opened_devices == []


async def test_stream_cap_frees_a_slot_when_a_viewer_disconnects() -> None:
    stop = asyncio.Event()
    server = await start_server(lambda: FAKE_FRAME, stop)
    api = api_for(server)
    streams = [await asyncio.to_thread(api.open_camera_stream) for _ in range(MAX_STREAMS)]
    try:
        with pytest.raises(DaemonApiError, match="429"):
            await asyncio.to_thread(api.open_camera_stream)
        streams.pop().close()
        streams.append(await _open_when_free(api))
    finally:
        for stream in streams:
            stream.close()
        stop.set()
        await server.close()


async def test_a_stalled_viewer_frees_its_slot(monkeypatch) -> None:
    # Regression: a viewer that stopped reading kept its slot (and held up shutdown).
    async def never_returns(self, data) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(camera_stream, "WRITE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(web.StreamResponse, "write", never_returns)
    stop = asyncio.Event()
    server = await start_server(lambda: FAKE_FRAME, stop)
    api = api_for(server)
    streams = [await asyncio.to_thread(api.open_camera_stream) for _ in range(MAX_STREAMS)]
    try:
        streams.append(await _open_when_free(api))
    finally:
        for stream in streams:
            stream.close()
        stop.set()
        await server.close()


async def _open_when_free(api: DaemonApi):
    """Open a stream, retrying on 429 until the server has noticed the closed one."""
    deadline = asyncio.get_running_loop().time() + SLOT_FREED_WITHIN_S
    while True:
        try:
            return await asyncio.to_thread(api.open_camera_stream)
        except DaemonApiError:
            if asyncio.get_running_loop().time() > deadline:
                raise
            await asyncio.sleep(0.1)
