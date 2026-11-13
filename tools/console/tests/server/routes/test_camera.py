"""The camera proxy: the whiteboard token never reaches the page; its limits come back in words."""

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from signal_console.server import SESSION_TOKEN_HEADER
from signal_console.server.routes.camera import NO_PICTURE, TOO_MANY_VIEWERS, UNEXPECTED
from signal_console.status.whiteboard_api import (
    TOKEN_HEADER,
    WHITEBOARD_DAEMON_FILE,
    WHITEBOARD_TOKEN_FILE,
)

WHITEBOARD_TOKEN = "whiteboard-secret-token-for-tests"
FRAME = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 4\r\n\r\nJPEG\r\n"


REDIRECT_TARGET = "/elsewhere/stream"


async def _one_frame(request: web.Request) -> web.StreamResponse:
    content_type = "multipart/x-mixed-replace; boundary=frame"
    response = web.StreamResponse(headers={"Content-Type": content_type})
    await response.prepare(request)
    await response.write(FRAME)
    return response


def _fake_whiteboard(status: int) -> web.Application:
    """A daemon that wants the token, then streams one frame, refuses with `status`, or
    (302) redirects to a route that would stream, which the proxy must never follow."""

    async def stream(request: web.Request) -> web.StreamResponse:
        if request.headers.get(TOKEN_HEADER) != WHITEBOARD_TOKEN:
            return web.json_response({"error": "missing or wrong X-Signal-Token"}, status=403)
        if status == 302:
            raise web.HTTPFound(REDIRECT_TARGET)
        if status != 200:
            return web.json_response({"error": "daemon wording"}, status=status)
        return await _one_frame(request)

    app = web.Application()
    app.router.add_get("/api/camera/stream", stream)
    app.router.add_get(REDIRECT_TARGET, _one_frame)
    return app


async def _start(console, status: int) -> TestServer:
    server = TestServer(_fake_whiteboard(status), host="127.0.0.1")
    await server.start_server()
    folder = console.services.whiteboard_dir
    folder.mkdir()
    (folder / WHITEBOARD_DAEMON_FILE).write_text(json.dumps({"port": server.port}))
    (folder / WHITEBOARD_TOKEN_FILE).write_text(WHITEBOARD_TOKEN)
    return server


async def test_the_stream_passes_through_without_the_whiteboard_token(console):
    server = await _start(console, 200)
    try:
        headers = {SESSION_TOKEN_HEADER: console.token}
        response = await console.client.get("/api/camera/stream", headers=headers)
        body = await response.read()
    finally:
        await server.close()
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("multipart/x-mixed-replace")
    assert body == FRAME
    page_sees = body.decode() + json.dumps(dict(response.headers))
    assert WHITEBOARD_TOKEN not in page_sees


@pytest.mark.parametrize(
    ("daemon_status", "expected_status", "words"),
    [
        (429, 429, TOO_MANY_VIEWERS),
        (503, 503, NO_PICTURE),
        # Regression: a redirect is never followed (the token would go with it).
        (302, 502, UNEXPECTED),
    ],
)
async def test_daemon_refusals_come_back_as_plain_words(
    console, daemon_status, expected_status, words
):
    server = await _start(console, daemon_status)
    try:
        headers = {SESSION_TOKEN_HEADER: console.token}
        response = await console.client.get("/api/camera/stream", headers=headers)
        payload = await response.json()
    finally:
        await server.close()
    assert (response.status, payload["error"]) == (expected_status, words)
