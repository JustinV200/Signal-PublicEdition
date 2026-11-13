"""run_whiteboard runs a real subprocess: its stdout, the CLI's error line, or a timeout kill."""

import sys

import psutil
import pytest

from signal_console.actions import StepFailed, run_whiteboard, whiteboard_cli

# Prints its first argument to stdout; with "fail", logs to stderr and exits 2 like the CLI.
SCRIPT = (
    "import sys\n"
    "if sys.argv[1] == 'fail':\n"
    "    print('INFO whiteboard: starting daemon', file=sys.stderr)\n"
    "    print('whiteboard: error: the daemon refused', file=sys.stderr)\n"
    "    sys.exit(2)\n"
    "print(sys.argv[1])\n"
)
FAKE_CLI = [sys.executable, "-c", SCRIPT]


async def test_run_whiteboard_returns_stdout():
    assert await run_whiteboard(["realigned"], FAKE_CLI) == "realigned"


async def test_run_whiteboard_raises_the_cli_error_line():
    with pytest.raises(StepFailed, match=r"^whiteboard: error: the daemon refused$"):
        await run_whiteboard(["fail"], FAKE_CLI)


# Starts a stand-in daemon (`... whiteboard.cli serve` in its command line) and a
# plain child, writes both pids to argv[1], then hangs like a stuck calibrate.
HANGING_CLI = (
    "import subprocess, sys, time\n"
    "sleeper = [sys.executable, '-c', 'import time; time.sleep(60)']\n"
    # Like the real daemon (it logs to a file), it holds none of the CLI's pipes.
    "quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
    "daemon = subprocess.Popen([*sleeper, 'whiteboard.cli', 'serve'], **quiet)\n"
    "child = subprocess.Popen(sleeper)\n"
    "open(sys.argv[1], 'w').write(f'{daemon.pid} {child.pid}')\n"
    "time.sleep(60)\n"
)


async def test_timeout_kills_the_cli_tree_but_not_the_daemon(tmp_path, monkeypatch):
    monkeypatch.setattr(whiteboard_cli, "TIMEOUT_S", 3.0)
    pid_file = tmp_path / "pids"
    with pytest.raises(StepFailed, match="didn't finish"):
        await run_whiteboard([str(pid_file)], [sys.executable, "-c", HANGING_CLI])

    daemon_pid, child_pid = (int(pid) for pid in pid_file.read_text().split())
    daemon = psutil.Process(daemon_pid)
    try:
        assert not psutil.pid_exists(child_pid)
        assert daemon.is_running()
    finally:
        daemon.kill()


def test_default_command_skips_the_venv_sync(monkeypatch):
    # Regression: a sync on every click failed while whiteboard.exe was in use.
    monkeypatch.setattr(whiteboard_cli.shutil, "which", lambda _name: "uv")
    command = whiteboard_cli._uv_whiteboard()
    assert "--no-sync" in command
    assert command.index("--no-sync") < command.index("whiteboard")
