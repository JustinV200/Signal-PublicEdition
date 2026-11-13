"""DaemonApi's error mapping, which decides when the clients may start a new daemon."""

import socket

import pytest

from whiteboard.daemon_client import DaemonApi, DaemonUnreachableError

# Far shorter than Windows takes to refuse a closed loopback port (~2 s), so the
# connect times out instead, the case that used to be misreported.
CONNECT_TIMEOUT_S = 0.05


def test_a_connect_timeout_or_refusal_counts_as_no_daemon() -> None:
    # Regression: a connect timeout was raised as DaemonApiError, so a stale token
    # file made every client fail instead of starting the daemon.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    api = DaemonApi(f"http://127.0.0.1:{closed_port}", token="t")
    with pytest.raises(DaemonUnreachableError):
        api.request("GET", "/api/status", timeout_s=CONNECT_TIMEOUT_S)
