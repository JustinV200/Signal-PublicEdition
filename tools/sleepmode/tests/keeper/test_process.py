"""Tests for ending a keeper that hangs on, against real but harmless windowless processes."""

import subprocess
import sys

from sleepmode.keeper import is_process_alive, process_creation_time, stop_keeper

CREATE_NO_WINDOW = 0x08000000
SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def _start(command: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )


def test_stop_keeper_ends_only_the_process_it_recorded() -> None:
    keeper = _start(SLEEPER)
    # This venv's python too (an MCP server, say), as if it had reused the keeper's pid.
    other = _start(SLEEPER)
    try:
        created = process_creation_time(keeper.pid)
        # status() asks this way, so a dead keeper's reused pid doesn't pass for it.
        assert is_process_alive(keeper.pid, created) and not is_process_alive(other.pid, created)
        stop_keeper(other.pid, created, wait_s=0.2)
        stop_keeper(keeper.pid, None, wait_s=0.2)  # an old state file with no start time
        assert keeper.poll() is None and other.poll() is None
        stop_keeper(keeper.pid, created, wait_s=0.2)
        assert keeper.wait(timeout=5) is not None
        assert other.poll() is None
    finally:
        keeper.kill()
        other.kill()
