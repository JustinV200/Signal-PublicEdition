"""DaemonConnection re-reads the state files and retries once when its token or port went stale."""

import http.server
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from whiteboard.daemon_client import (
    DaemonApi,
    DaemonAuthError,
    DaemonConnection,
    DaemonLocation,
    write_daemon_info,
)


class _Handler(http.server.BaseHTTPRequestHandler):
    """Answers {"ok": true} when X-Signal-Token matches the server's token.

    Otherwise it sends 403 with {"ok": false, "error": "wrong token"}.
    """

    def do_GET(self) -> None:
        good = self.headers.get("X-Signal-Token") == self.server.token  # type: ignore[attr-defined]
        self.send_response(200 if good else 403)
        self.end_headers()
        self.wfile.write(json.dumps({"ok": good, "error": "wrong token"}).encode())

    def log_message(self, *args: object) -> None:
        """Keep test output quiet."""


@contextmanager
def fake_daemon(token: str) -> Iterator[http.server.ThreadingHTTPServer]:
    """Run a token-checking server on a free loopback port."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.token = token  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def publish(state_dir: Path, server: http.server.HTTPServer, token: str) -> None:
    """Write daemon.json and token the way a daemon start would."""
    write_daemon_info(state_dir, server.server_address[1])
    (state_dir / "token").write_text(token, encoding="utf-8")


def make_connection(state_dir: Path) -> DaemonConnection:
    return DaemonConnection(DaemonLocation(state_dir, port=1), is_auto_start=False)


def test_concurrent_calls_survive_a_token_rotation(tmp_path: Path) -> None:
    """A restart keeps the port and rotates the token; parallel 403s must all recover."""
    connection = make_connection(tmp_path)
    with fake_daemon("old") as server:
        publish(tmp_path, server, "old")
        stale: list[DaemonApi] = []
        connection.call(stale.append)  # caches the client that holds the old token
        server.token = "new"  # type: ignore[attr-defined]
        publish(tmp_path, server, "new")
        # Both threads must hold the stale client before either refreshes.
        both_hold_stale = threading.Barrier(2, timeout=10)
        results: list[bool] = []

        def operation(api: DaemonApi) -> dict[str, object]:
            if api is stale[0]:
                both_hold_stale.wait()
            return api.status()

        def worker() -> None:
            results.append(bool(connection.call(operation)["ok"]))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
    assert results == [True, True]


def test_a_real_403_with_unchanged_token_is_raised_without_looping(tmp_path: Path) -> None:
    connection = make_connection(tmp_path)
    with fake_daemon("right") as server:
        publish(tmp_path, server, "right")
        connection.call(lambda api: api.status())
        server.token = "different"  # type: ignore[attr-defined]  # files still say "right"
        calls: list[int] = []

        def operation(api: DaemonApi) -> dict[str, object]:
            calls.append(1)
            return api.scene()

        with pytest.raises(DaemonAuthError):
            connection.call(operation)
    # One try, then one re-read that found nothing new: no retry.
    assert len(calls) == 1
