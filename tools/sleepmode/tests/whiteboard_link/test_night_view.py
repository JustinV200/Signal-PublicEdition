"""Tests for the night view client against a fake whiteboard daemon on a loopback port."""

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from sleepmode.whiteboard_link import (
    KIOSK_OPEN_PATH,
    SHOW_PATH,
    TOKEN_HEADER,
    NightViewClient,
    WhiteboardUnavailableError,
    night_seed,
    repair_night_view,
)

TOKEN = "test-token"


class FakeDaemon(BaseHTTPRequestHandler):
    """Answers POSTs: 404 for unknown paths, ok:false for a wrong token, else ok:true.
    GET /api/status answers with `status`."""

    routes = {"/api/night/show", "/api/night/hide", "/api/kiosk/open"}
    token = TOKEN
    received: list[tuple[str, str | None, dict]] = []
    status: dict = {}

    def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
        reply = json.dumps({"ok": True, **FakeDaemon.status}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(reply)

    def do_POST(self) -> None:  # noqa: N802 (http.server's naming)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeDaemon.received.append((self.path, self.headers.get(TOKEN_HEADER), body))
        if self.path not in FakeDaemon.routes:
            self.send_error(404)
            return
        reply = json.dumps({"ok": self.headers.get(TOKEN_HEADER) == FakeDaemon.token}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *_args: object) -> None:
        """Keep test output quiet."""


@pytest.fixture
def daemon_state(tmp_path: Path) -> Iterator[Path]:
    """A whiteboard .state/ folder pointing at a fake daemon that's running."""
    FakeDaemon.received = []
    FakeDaemon.routes = {"/api/night/show", "/api/night/hide", "/api/kiosk/open"}
    FakeDaemon.token = TOKEN
    FakeDaemon.status = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDaemon)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon = {"pid": os.getpid(), "port": server.server_port}
    (tmp_path / "daemon.json").write_text(json.dumps(daemon))
    (tmp_path / "token").write_text(TOKEN + "\n")
    yield tmp_path
    server.shutdown()
    server.server_close()


def test_show_and_hide_send_the_contract(daemon_state: Path) -> None:
    client = NightViewClient(daemon_state)
    client.show(20261019)
    client.hide()
    assert FakeDaemon.received == [
        (SHOW_PATH, TOKEN, {"seed": 20261019}),
        ("/api/night/hide", TOKEN, {}),
    ]


@pytest.mark.parametrize(
    ("status", "is_showing"),
    [
        ({"view": "night", "pages_connected": 1}, True),
        ({"view": "night", "pages_connected": 0}, False),  # its kiosk has closed
        ({"view": "drawing", "pages_connected": 1}, False),
    ],
)
def test_is_showing_needs_the_night_view_on_a_page(
    daemon_state: Path, status: dict, is_showing: bool
) -> None:
    FakeDaemon.status = status
    assert NightViewClient(daemon_state).is_showing() is is_showing


def test_a_restarted_daemon_is_followed_without_a_new_client(daemon_state: Path) -> None:
    client = NightViewClient(daemon_state)
    client.show(1)
    FakeDaemon.token = "rotated"  # the daemon restarted with a new token
    (daemon_state / "token").write_text("rotated\n")
    client.hide()  # reads the files again, so no stale token
    assert [token for _path, token, _body in FakeDaemon.received] == [TOKEN, "rotated"]


def _no_night_view_routes(_state: Path) -> None:
    FakeDaemon.routes = set()  # an older whiteboard: 404


def _stale_token(state: Path) -> None:
    (state / "token").write_text("stale")  # the daemon answers ok:false


def _no_discovery_files(state: Path) -> None:
    (state / "daemon.json").unlink()  # the daemon isn't running


def _nothing_listening(state: Path) -> None:
    (state / "daemon.json").write_text(json.dumps({"port": 1}))


def _daemon_exited(state: Path) -> None:
    # A crashed daemon's daemon.json is left behind; its port may still answer here.
    info = json.loads((state / "daemon.json").read_text())
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()
    (state / "daemon.json").write_text(json.dumps({**info, "pid": process.pid}))


@pytest.mark.parametrize(
    "break_whiteboard",
    [_no_night_view_routes, _stale_token, _no_discovery_files, _nothing_listening, _daemon_exited],
)
def test_every_failure_is_unavailable(daemon_state: Path, break_whiteboard) -> None:
    break_whiteboard(daemon_state)
    with pytest.raises(WhiteboardUnavailableError):
        NightViewClient(daemon_state, timeout_s=1.0).show(1)


@pytest.mark.parametrize(
    ("is_daemon_up", "starts", "posted"),
    [
        (False, 1, []),  # the daemon is down: start it
        (True, 0, [(KIOSK_OPEN_PATH, TOKEN, {})]),  # up with no page: reopen its kiosk
    ],
)
def test_repair_starts_a_down_daemon_or_reopens_the_kiosk(
    daemon_state: Path, is_daemon_up: bool, starts: int, posted: list
) -> None:
    if not is_daemon_up:
        (daemon_state / "daemon.json").unlink()
    started = []
    repair_night_view(NightViewClient(daemon_state), lambda: started.append(True) or True)
    assert (len(started), FakeDaemon.received) == (starts, posted)


def test_night_seed_changes_at_noon_not_midnight() -> None:
    assert night_seed(datetime(2026, 10, 19, 22, 0)) == 20261019
    assert night_seed(datetime(2026, 10, 20, 3, 0)) == 20261019
    assert night_seed(datetime(2026, 10, 20, 21, 0)) == 20261020
