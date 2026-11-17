"""Daemon lifecycle (serve.py): a failed startup undoes itself, and shutdown keeps finished runs."""

import asyncio
import importlib

import pytest

from analysis_chamber.daemon import start_daemon
from analysis_chamber.runs import Manifest, Status, create_run_dir, read_manifest, write_manifest


@pytest.mark.asyncio
async def test_failed_startup_stops_resumed_runs_and_frees_the_lock(
    config, phases, monkeypatch
) -> None:
    run_id = "2026-11-01-a"
    manifest = Manifest(run_id, "q", plan_text="PLAN", personal=True, status=Status.RUNNING)
    write_manifest(create_run_dir(config.private_root, run_id), manifest)

    def refuse(*args) -> None:
        raise OSError("disk full")

    # The module, not the `serve` function the package exports under the same name.
    serve_module = importlib.import_module("analysis_chamber.daemon.serve")
    monkeypatch.setattr(serve_module, "write_state", refuse)
    with pytest.raises(OSError, match="disk full"):
        await start_daemon(config, phases.backend())
    # The resumed run was stopped like a shutdown: no task left, not cancelled.
    assert phases.started and not [
        t for t in asyncio.all_tasks() if t.get_name() == f"run-{run_id}"
    ]
    assert read_manifest(config.private_root / run_id).status is Status.RUNNING
    assert phases.closed == []

    monkeypatch.undo()
    again = await start_daemon(config, phases.backend())  # the lock was freed
    await again.close()


@pytest.mark.asyncio
async def test_shutdown_after_done_keeps_the_run_done(config, phases, wait_until) -> None:
    async def done_then_notify(ctx, agents, hooks) -> None:
        ctx.manifest.status, ctx.manifest.percent = Status.DONE, 100
        await hooks.on_update(ctx.manifest)
        await asyncio.sleep(1)  # notifier.done's console subprocess, cut off by shutdown

    phases.run_pipeline = done_then_notify
    daemon = await start_daemon(config, phases.backend())
    run_id = (await daemon.chamber.start("q"))["run_id"]
    await daemon.chamber.approve(run_id, None, True)
    manifest_dir = config.private_root / run_id
    await wait_until(lambda: read_manifest(manifest_dir).status is Status.DONE)
    await daemon.close()

    assert daemon.chamber.status(run_id)["status"] == "done"
    assert read_manifest(manifest_dir).status is Status.DONE
