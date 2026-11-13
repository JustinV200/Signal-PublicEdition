"""A voice start is done only once the hub listens; a hub that dies first fails with its log."""

import os

import pytest

from signal_console.actions import StepFailed
from signal_console.actions.plans import HubStep
from signal_console.actions.steps import ActionTools, run_step
from signal_console.hub import HubRecord
from signal_console.hub import process as hub_process
from signal_console.paths import HUB_LOG_FILE


async def test_a_hub_that_exits_while_starting_fails_with_its_last_log_line(tmp_path, monkeypatch):
    async def never_listening():
        return False

    monkeypatch.setattr(hub_process, "is_hub_listening", never_listening)
    (tmp_path / HUB_LOG_FILE).write_text(
        "Traceback (most recent call last):\n  ...\nRuntimeError: CUDA failed\n\n", encoding="utf-8"
    )
    # Our own pid with the wrong start time: the recorded process is gone.
    tools = ActionTools(start_hub=lambda state_dir: HubRecord(os.getpid(), 0.0))

    with pytest.raises(StepFailed, match="RuntimeError: CUDA failed"):
        await run_step(HubStep(start=True), tmp_path, tools)
