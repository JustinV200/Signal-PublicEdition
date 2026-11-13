"""Tests for starting the whiteboard daemon for sleep, with a fake popen (nothing starts)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import sleepmode.whiteboard_link.daemon_start as daemon_start
from sleepmode.whiteboard_link import start_whiteboard_if_down


def _exited_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()
    return process.pid


@pytest.fixture
def launches(monkeypatch) -> list[tuple[list[str], Path]]:
    """Each (command, cwd) popen_detached was given; no process is started."""
    calls: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(
        daemon_start,
        "popen_detached",
        lambda command, flags, cwd, output: calls.append((command, cwd)),
    )
    return calls


def test_a_running_daemon_is_left_alone(tmp_path: Path, launches) -> None:
    (tmp_path / "daemon.json").write_text(json.dumps({"pid": os.getpid(), "port": 8765}))

    assert start_whiteboard_if_down(tmp_path, Path("wb")) is False
    assert launches == []


@pytest.mark.parametrize("daemon_info", [None, "{not json", "exited"])
def test_a_missing_or_dead_daemon_is_started_once(tmp_path, launches, daemon_info) -> None:
    state = tmp_path / ".state"
    if daemon_info is not None:
        state.mkdir()
        text = json.dumps({"pid": _exited_pid()}) if daemon_info == "exited" else daemon_info
        (state / "daemon.json").write_text(text)

    assert start_whiteboard_if_down(state, Path("wb")) is True
    # The whiteboard's own CLI through uv, never its code; its output goes to its log.
    assert launches == [
        (["uv", "run", "--project", "wb", "--frozen", "whiteboard", "serve"], Path("wb"))
    ]
    assert (state / "daemon.log").exists()
