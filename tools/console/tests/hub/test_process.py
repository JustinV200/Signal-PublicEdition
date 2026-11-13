"""Stopping the hub kills only its own processes: never a reused pid, a non-hub or its daemons.

Stop takes the console's hub first, else the hub's own record (a hub started
elsewhere, or after a crashed console hub), in one call. It asks the hub to exit
cleanly first; the shutdown request is always a fake here, so a real hub is never stopped.
"""

import contextlib
import json
import subprocess
import sys

import psutil
import pytest

from signal_console.hub import process as hub_process
from signal_console.hub import stop_hub
from signal_console.paths import HUB_FILE
from signal_console.state_files import write_json

# Stands in for the hub: starts a detached daemon (as the whiteboard MCP server does), prints
# its pid and waits. It runs from the test's "audiohub" folder; the daemon doesn't.
FAKE_HUB = """
import subprocess, sys, time
flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
daemon = subprocess.Popen(sleeper, creationflags=flags)
print(daemon.pid, flush=True)
time.sleep(60)
"""
SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """A running fake hub under a test "audiohub" folder: (its top process, its daemon)."""
    hub_root = tmp_path / "audiohub"
    hub_root.mkdir()
    (hub_root / "hub.py").write_text(FAKE_HUB, encoding="utf-8")
    monkeypatch.setattr(hub_process, "AUDIOHUB_ROOT", hub_root)
    hub = subprocess.Popen([sys.executable, str(hub_root / "hub.py")], stdout=subprocess.PIPE)
    daemon = psutil.Process(int(hub.stdout.readline()))
    try:
        yield psutil.Process(hub.pid), daemon
    finally:
        _kill_tree_quietly(daemon)
        hub.kill()
        hub.wait()
        hub.stdout.close()


@pytest.fixture
def bystander():
    """An unrelated running process, outside the "audiohub" folder."""
    process = subprocess.Popen(SLEEPER)
    try:
        yield psutil.Process(process.pid)
    finally:
        process.kill()
        process.wait()


# (console record, hub's own record, is a hub killed). "hub"/"bystander" name the process a
# record points at; "+old" gives it a start time that doesn't match (a reused pid).
STOP_CASES = {
    "console hub": ("hub", None, True),
    "hub started elsewhere": (None, "hub", True),
    "stale console record, hub started elsewhere": ("bystander+old", "hub", True),
    "reused pid in the hub's record": (None, "hub+old", False),
    "not the hub in the hub's record": (None, "bystander", False),
}


@pytest.mark.parametrize(
    ("console_record", "hub_record", "is_killed"), STOP_CASES.values(), ids=STOP_CASES.keys()
)
def test_stop_kills_only_a_verified_hub_in_one_call(
    tmp_path, fake_hub, bystander, console_record, hub_record, is_killed
):
    hub, daemon = fake_hub
    targets = {"hub": hub, "bystander": bystander}
    if console_record:
        write_json(tmp_path / HUB_FILE, _record(targets, console_record, "createTime"))
    hub_record_path = tmp_path / "audiohub-hub.json"
    hub_record_path.write_text(json.dumps(_record(targets, hub_record, "create_time")))
    hub_chain = [hub, *hub.children()]  # the venv's python.exe redirector and its interpreter

    assert stop_hub(tmp_path, hub_record_path, lambda: False) is is_killed

    assert any(member.is_running() for member in hub_chain) is not is_killed
    assert bystander.is_running()
    assert daemon.is_running()
    assert hub_record_path.exists()  # readers never delete the hub's own record
    assert not (tmp_path / HUB_FILE).exists()


@pytest.mark.parametrize("hub_exits", [True, False], ids=["exits when asked", "ignores it"])
def test_stop_asks_the_hub_to_exit_and_kills_it_only_if_it_stays(
    tmp_path, fake_hub, monkeypatch, hub_exits
):
    hub, _ = fake_hub
    write_json(tmp_path / HUB_FILE, {"pid": hub.pid, "createTime": hub.create_time()})
    hub_chain = [hub, *hub.children()]
    monkeypatch.setattr(hub_process, "GRACEFUL_EXIT_TIMEOUT_S", 0.5)
    killed = []
    real_kill_tree = hub_process._kill_tree
    monkeypatch.setattr(
        hub_process,
        "_kill_tree",
        lambda process: killed.append(process.pid) or real_kill_tree(process),
    )

    def request_shutdown():
        if hub_exits:  # the hub exits by itself, as audiohub does after replying
            for member in hub_chain:
                _kill_tree_quietly(member)
        return True

    assert stop_hub(tmp_path, tmp_path / "no-record.json", request_shutdown) is True
    assert killed == ([] if hub_exits else [hub.pid])
    assert not any(member.is_running() for member in hub_chain)
    assert not (tmp_path / HUB_FILE).exists()


def _record(targets, spec, time_key):
    if spec is None:
        return {}
    name, _, old = spec.partition("+")
    process = targets[name]
    return {"pid": process.pid, time_key: process.create_time() - (100 if old else 0)}


def _kill_tree_quietly(process):
    try:
        members = [*process.children(recursive=True), process]
    except psutil.NoSuchProcess:
        return  # Already gone (the stop killed it).
    for member in members:
        with contextlib.suppress(psutil.NoSuchProcess):
            member.kill()
