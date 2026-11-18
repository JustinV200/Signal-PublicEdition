"""Progress: resume after a stop, optional skips, skipped tools, Windows-only steps."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from signal_setup import progress, registry
from signal_setup.cli.agent import AgentAsker
from signal_setup.steps import run


def test_tool_status_through_a_resumed_setup(tmp_path: Path) -> None:
    calendar = registry.by_id("calendar")
    data = progress.load(tmp_path)
    assert progress.tool_status(data, calendar, "windows") == ""
    progress.set_step(data, "calendar", "install", progress.DONE)
    progress.save(tmp_path, data)  # setup stopped here

    data = progress.load(tmp_path)
    assert progress.tool_status(data, calendar, "windows") == "started"
    for step in ("google-api", "signin"):
        progress.set_step(data, "calendar", step, progress.DONE)
    progress.set_step(data, "calendar", "schedule", progress.SKIPPED)  # optional
    assert progress.tool_status(data, calendar, "windows") == progress.DONE

    progress.set_skipped(data, "calendar")
    assert progress.tool_status(data, calendar, "windows") == progress.SKIPPED
    progress.set_step(data, "calendar", "install", progress.DONE)  # re-running un-skips
    assert progress.tool_status(data, calendar, "windows") == progress.DONE


@pytest.mark.parametrize("settled", [progress.DONE, progress.SKIPPED])
def test_tool_with_only_optional_steps_is_done_once_one_is_settled(tmp_path, settled) -> None:
    # Regression: picking copytone (two optional steps) read done before anything happened.
    copytone = registry.by_id("copytone")
    data = progress.load(tmp_path)
    progress.set_skipped(data, "copytone", False)  # what picking it records
    assert progress.tool_status(data, copytone, "windows") == progress.STARTED

    progress.set_step(data, "copytone", "voice-test", settled)
    assert progress.tool_status(data, copytone, "windows") == progress.DONE


def test_scheduled_task_steps_only_apply_on_windows() -> None:
    steps = {s.id for s in progress.applicable_steps(registry.by_id("calendar"), "linux")}
    assert "schedule" not in steps and "install" in steps


def test_run_steps_start_the_resolved_program(tmp_path: Path, monkeypatch) -> None:
    # Regression: a bare "npm" can't start on Windows (npm.cmd isn't an .exe).
    started = []
    monkeypatch.setattr(run.shutil, "which", lambda name: rf"C:\nodejs\{name}.CMD")
    monkeypatch.setattr(
        run.subprocess,
        "run",
        lambda argv, cwd: started.append(argv) or SimpleNamespace(returncode=0),
    )
    console = registry.by_id("console")

    status = run.run_step(
        tmp_path, console, console.step("web-deps"), progress.load(tmp_path), AgentAsker(None, None)
    )

    assert status == progress.DONE
    assert started[0][0] == r"C:\nodejs\npm.CMD"
