"""Tests for mail_digest.child_env: clean child environments and a helper timeout that holds."""

import sys
import tempfile
import time

from mail_digest.child_env import clean_env, run_hidden

# A CLI whose own child would outlive a plain kill with the CLI's stdout and stderr,
# as uv run's python child does. The child touches the file in argv[1] unless killed.
LINGERING_CHILD = (
    "import subprocess, sys, time; "
    "subprocess.Popen([sys.executable, '-c', 'import pathlib, sys, time; "
    "time.sleep(3); pathlib.Path(sys.argv[1]).touch()', sys.argv[1]],"
    " stdout=sys.stdout, stderr=sys.stderr); "
    "time.sleep(8)"
)


def test_clean_env_drops_parent_session_variables_only():
    env = {
        "PATH": "p",
        "ANTHROPIC_API_KEY": "k",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_MESSAGING_SOCKET": "pipe",
        "MCP_CONNECTION_NONBLOCKING": "true",
    }
    assert clean_env(env) == {"PATH": "p", "ANTHROPIC_API_KEY": "k"}


def test_run_hidden_kills_the_cli_and_its_children_at_its_timeout(tmp_path):
    survived = tmp_path / "child-survived"
    started = time.monotonic()
    argv = [sys.executable, "-c", LINGERING_CHILD, str(survived)]
    assert run_hidden("lingering cli", argv, 1) is False
    assert time.monotonic() - started < 5
    time.sleep(4)  # past the moment the child would have touched the file
    assert not survived.exists()


def test_run_hidden_is_false_not_raising_when_its_output_files_cant_be_made(monkeypatch):
    def full_temp_folder():
        raise OSError("No space left on device")

    monkeypatch.setattr(tempfile, "TemporaryFile", full_temp_folder)
    assert run_hidden("any cli", [sys.executable, "-c", "pass"], 5) is False
