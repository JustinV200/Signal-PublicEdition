"""Local callers only talk to the port in daemon.json while the server that wrote it still runs."""

import os
import socket

import psutil
import pytest

from signal_console.local_api import HOOK_TURN_PATH, ConsoleNotRunningError, post_local
from signal_console.paths import DAEMON_FILE, LOCAL_KEY_FILE, LOOPBACK_HOST
from signal_console.state_files import write_json, write_secret


def test_a_stale_daemon_record_sends_nothing_to_whatever_holds_its_port(tmp_path):
    with socket.create_server((LOOPBACK_HOST, 0)) as squatter:
        squatter.setblocking(False)
        # This pid with another start time: as if the server died and its pid was reused.
        stale_time = psutil.Process().create_time() - 100
        record = {"pid": os.getpid(), "createTime": stale_time, "port": squatter.getsockname()[1]}
        write_json(tmp_path / DAEMON_FILE, record)
        write_secret(tmp_path / LOCAL_KEY_FILE, "local-key")

        with pytest.raises(ConsoleNotRunningError):
            post_local(tmp_path, HOOK_TURN_PATH, {"text": "the reply"}, 0.5)
        # Nothing ever connected, so neither the key nor the reply went out.
        with pytest.raises(BlockingIOError):
            squatter.accept()
