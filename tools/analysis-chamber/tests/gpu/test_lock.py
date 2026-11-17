"""Tests for analysis_chamber.gpu: exclusivity across real processes, timeout, run_locked."""

import subprocess
import sys
import time

import pytest

from analysis_chamber.gpu import GpuLockTimeout, gpu_lock, lock, run_locked

# A child that takes the lock, announces it, and holds it until stdin gets a line.
HOLDER = (
    "import sys; from pathlib import Path; from analysis_chamber.gpu import gpu_lock\n"
    "with gpu_lock(Path(sys.argv[1])):\n"
    "    print('held', flush=True); sys.stdin.readline()\n"
)


def _start_holder(state_dir):
    child = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(state_dir)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout.readline().strip() == "held"
    return child


def test_lock_excludes_other_process_then_frees(tmp_path):
    child = _start_holder(tmp_path)
    try:
        with pytest.raises(GpuLockTimeout), gpu_lock(tmp_path, timeout_s=0.5):
            pass
    finally:
        child.communicate("\n", timeout=10)


def test_lock_is_freed_when_holder_is_killed(tmp_path):
    child = _start_holder(tmp_path)
    child.kill()
    child.wait()
    with gpu_lock(tmp_path, timeout_s=5):
        pass


def test_run_locked_returns_exit_code(tmp_path):
    assert run_locked(tmp_path, [sys.executable, "-c", "raise SystemExit(3)"]) == 3


# A wrapper that runs a sleeping child under the lock and prints the child's pid.
WRAPPER = (
    "import sys; from pathlib import Path; from analysis_chamber.gpu import run_locked\n"
    "run_locked(Path(sys.argv[1]), [sys.executable, '-c',\n"
    "    'import os, time; print(os.getpid(), flush=True); time.sleep(60)'])\n"
)


def _is_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
    return str(pid) in out.stdout


def test_run_locked_child_dies_when_wrapper_is_killed(tmp_path):
    wrapper = subprocess.Popen(
        [sys.executable, "-c", WRAPPER, str(tmp_path)], stdout=subprocess.PIPE, text=True
    )
    child_pid = int(wrapper.stdout.readline())
    wrapper.kill()
    wrapper.wait()
    deadline = time.monotonic() + 10
    while _is_alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _is_alive(child_pid)


def test_run_locked_kills_child_and_frees_lock_when_job_add_fails(tmp_path, monkeypatch):
    started = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        started.append(real_popen(*args, **kwargs))
        return started[-1]

    def failing_add(self, handle):
        raise OSError("job refused")

    monkeypatch.setattr(lock.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(lock.KillOnCloseJob, "add", failing_add)
    begin = time.monotonic()
    with pytest.raises(OSError, match="job refused"):
        run_locked(tmp_path, [sys.executable, "-c", "import time; time.sleep(60)"])
    assert time.monotonic() - begin < 10
    assert started[0].poll() is not None  # child was killed, not left sleeping
    with gpu_lock(tmp_path, timeout_s=2):  # lock was released
        pass
