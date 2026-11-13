"""spawn_daemon: leaves the caller's job when it can, falls back when it can't, rotates the log."""

import subprocess

import pytest

from whiteboard.daemon_client import connection
from whiteboard.daemon_client.connection import DaemonLocation, spawn_daemon


@pytest.mark.parametrize("is_breakaway_denied", [False, True])
def test_spawn_breaks_away_from_the_job_or_falls_back(
    tmp_path, monkeypatch, is_breakaway_denied: bool
) -> None:
    flags_tried: list[int] = []

    def fake_popen(command, **kwargs):
        flags_tried.append(kwargs["creationflags"])
        if is_breakaway_denied and kwargs["creationflags"] & subprocess.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError(13, "Access is denied")
        return "process"

    monkeypatch.setattr(connection.subprocess, "Popen", fake_popen)
    old_log = tmp_path / "daemon.log"
    old_log.write_bytes(b"x" * (connection.LOG_ROTATE_BYTES + 1))
    assert spawn_daemon(DaemonLocation(tmp_path, 8770)) == "process"
    expected = [connection.BREAKAWAY_FLAGS]
    if is_breakaway_denied:
        expected.append(connection.DETACHED_FLAGS)
    assert flags_tried == expected
    # The oversized log moved aside; the new daemon starts a fresh one.
    assert (tmp_path / "daemon.log.1").stat().st_size > connection.LOG_ROTATE_BYTES
    assert old_log.stat().st_size == 0
