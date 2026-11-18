"""KioskWatchdog and POST /api/kiosk/open: a closed kiosk is reopened, with backoff while
reopening doesn't help, and the route needs the daemon token."""

import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from whiteboard.daemon.kiosk import KioskWatchdog, add_kiosk_routes
from whiteboard.daemon.kiosk.watchdog import CONFIRM_S
from whiteboard.daemon.request_guard import build_request_guard


class FakeKiosk:
    """Counts opens; raises OSError while `is_broken`."""

    def __init__(self) -> None:
        self.opens = 0
        self.is_broken = False

    def open(self) -> None:
        self.opens += 1
        if self.is_broken:
            raise OSError("Edge won't start")


def test_watchdog_reopens_a_closed_kiosk_and_backs_off_while_it_stays_gone() -> None:
    kiosk, pages, now = FakeKiosk(), [0], [0.0]
    waits: list[float] = []
    watchdog = KioskWatchdog(kiosk, lambda: pages[0], lambda: now[0], waits.append)
    kiosk.is_broken = True
    # Checks every 30 s with no page: opens at 0, 30, 90 and 210 s (30, 60, 120 s apart).
    opened_at = []
    for tick in range(8):
        now[0] = tick * 30.0
        if watchdog.check():
            opened_at.append(now[0])
    assert opened_at == [0.0, 30.0, 90.0, 210.0] and kiosk.opens == 4
    # Only the start-up open skips the re-check before relaunching.
    assert waits == [CONFIRM_S] * 3
    # A connected page resets it: the next time the kiosk closes, it's reopened at once.
    pages[0] = 1
    now[0] = 240.0
    assert watchdog.check() is False
    pages[0], now[0] = 0, 270.0
    assert watchdog.check() is True and kiosk.opens == 5


def test_watchdog_leaves_a_page_that_reconnects_alone_and_stops_for_good() -> None:
    kiosk, pages, now, waits = FakeKiosk(), [0], [0.0], []

    def wait(seconds: float) -> None:
        # The page comes back while the watchdog waits (a reload, a dropped socket).
        waits.append(seconds)
        pages[0] = 1

    watchdog = KioskWatchdog(kiosk, lambda: pages[0], lambda: now[0], wait)
    assert watchdog.check() is True and waits == []  # the start-up open
    pages[0], now[0] = 0, 60.0  # past the backoff
    assert watchdog.check() is False and waits == [CONFIRM_S] and kiosk.opens == 1
    pages[0] = 0  # gone for real, but stopped
    watchdog.stop()
    assert watchdog.check() is False and kiosk.opens == 1


@pytest.mark.asyncio
async def test_kiosk_open_route_needs_the_token_and_refuses_after_stop() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    kiosk = FakeKiosk()
    app = web.Application(middlewares=[build_request_guard("s3cret", port)])
    watchdog = KioskWatchdog(kiosk, lambda: 0)
    add_kiosk_routes(app, watchdog)
    client = TestClient(TestServer(app, host="127.0.0.1", port=port))
    await client.start_server()
    try:
        refused = await client.post("/api/kiosk/open", json={})
        refused_opens = kiosk.opens
        opened = await client.post("/api/kiosk/open", headers={"X-Signal-Token": "s3cret"})
        reply = await opened.json()
        watchdog.stop()
        stopped = await client.post("/api/kiosk/open", headers={"X-Signal-Token": "s3cret"})
    finally:
        await client.close()
    assert refused.status == 403 and refused_opens == 0
    assert reply == {"ok": True, "opened": True} and kiosk.opens == 1
    assert stopped.status == 409 and kiosk.opens == 1
