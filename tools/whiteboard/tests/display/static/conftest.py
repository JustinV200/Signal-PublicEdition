"""Shared fixture for the board page's JS tests: serve the static folder and a harness
page to headless Edge and hand back the JSON the harness POSTs to /result. Edge's
--dump-dom is no use here: msedge.exe hands the launch to a detached child, so the
launcher's stdout stays empty. A test is skipped where Edge isn't installed or never
calls back (some sandboxes stop it from starting).
"""

import asyncio
import socket
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from aiohttp import web

from whiteboard.display import STATIC_DIR
from whiteboard.display.screen import EdgeNotFoundError, close_kiosk, find_edge

EDGE_TIMEOUT_S = 60

RunHarness = Callable[[str], Awaitable[dict]]


@pytest.fixture
def run_harness(tmp_path: Path) -> RunHarness:
    """run_harness(html) -> the JSON the page POSTed to /result, via headless Edge."""
    try:
        edge = find_edge()
    except EdgeNotFoundError:
        pytest.skip("Microsoft Edge isn't installed")

    async def run(page: str) -> dict:
        served = asyncio.Event()  # set once Edge has fetched the harness page
        try:
            return await _serve_and_wait(edge, page, tmp_path / "edge", served)
        except TimeoutError:
            if served.is_set():
                pytest.fail("harness ran but never posted")
            pytest.skip("headless Edge didn't run here (sandboxed?)")

    return run


async def _serve_and_wait(
    edge: Path, page: str, profile: Path, served: asyncio.Event | None = None
) -> dict:
    """Serve `page` at /harness next to /static/ on a free loopback port, open it in
    headless Edge and return the first JSON body POSTed to /result."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    posted: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    async def harness(_: web.Request) -> web.Response:
        if served is not None:
            served.set()
        return web.Response(text=page, content_type="text/html")

    async def result(request: web.Request) -> web.Response:
        if not posted.done():
            posted.set_result(await request.json())
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/harness", harness)
    app.router.add_post("/result", result)
    app.router.add_static("/static/", STATIC_DIR)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    try:
        _open_headless(edge, f"http://127.0.0.1:{port}/harness", profile)
        return await asyncio.wait_for(posted, EDGE_TIMEOUT_S)
    finally:
        await runner.cleanup()
        # The browser outlives the launcher; close_kiosk finds it by its profile dir.
        await asyncio.to_thread(close_kiosk, profile)


def _open_headless(edge: Path, url: str, profile: Path) -> None:
    """Start headless Edge on `url` with its own profile. The launcher exits at once."""
    subprocess.Popen(
        [
            str(edge),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            f"--user-data-dir={profile}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
