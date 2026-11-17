"""Daemon run flow: plan check rules, the queue cap, startup resume and the leak guard."""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from analysis_chamber.daemon import DaemonClient, DaemonError, start_daemon
from analysis_chamber.daemon.engine import Chamber, ChamberError
from analysis_chamber.guard import LeakError, is_under
from analysis_chamber.runs import (
    Manifest,
    Phase,
    Status,
    create_run_dir,
    read_manifest,
    write_manifest,
)


async def call(client: DaemonClient, method: str, *args, **kwargs) -> dict:
    """Run a blocking client call off the event loop the daemon serves on."""
    return await asyncio.to_thread(getattr(client, method), *args, **kwargs)


@pytest.mark.asyncio
async def test_approve_needs_personal_and_edits_keep_it_unapproved(daemon, client) -> None:
    started = await call(client, "start", "Median rent?")
    run_id = started["run_id"]
    assert started["plan"] == "PLAN: Median rent?"
    for bad in ({}, {"personal": "yes"}):
        with pytest.raises(DaemonError, match="personal yes/no"):
            await call(client, "approve", run_id, **bad)
    revised = await call(client, "approve", run_id, edits="add FRED data", personal=False)
    assert revised["plan"] == "REVISED: add FRED data"
    status = await call(client, "status", run_id)
    assert status["status"] == "awaiting_approval" and status["personal"] is None


@pytest.mark.asyncio
async def test_fourth_run_queues_until_a_slot_frees(daemon, client, phases, wait_until) -> None:
    run_ids = [(await call(client, "start", f"question {n}"))["run_id"] for n in range(4)]
    replies = [await call(client, "approve", run_id, personal=True) for run_id in run_ids]
    assert [reply["queue_position"] for reply in replies] == [None, None, None, 1]
    await wait_until(lambda: len(phases.started) == 3)
    assert (await call(client, "status", run_ids[3]))["status"] == "queued"

    cancelled = await call(client, "cancel", run_ids[0])
    assert cancelled["status"] == "cancelled" and phases.closed == [run_ids[0]]
    await wait_until(lambda: len(phases.started) == 4)
    fourth = await call(client, "status", run_ids[3])
    assert fourth["status"] == "running" and fourth["queue_position"] is None

    phases.gate.set()
    for run_id in run_ids[1:]:
        await wait_until(lambda run_id=run_id: daemon.chamber.status(run_id)["status"] == "done")


@pytest.mark.asyncio
async def test_resume_requeues_interrupted_runs_and_leaves_plans_waiting(
    config, phases, wait_until
) -> None:
    on_disk = [
        ("2026-11-01-b", Status.QUEUED, [], "2026-11-01T10:00:00+00:00"),
        ("2026-11-01-a", Status.RUNNING, ["plan", "collect"], "2026-11-01T09:00:00+00:00"),
        ("2026-11-01-c", Status.AWAITING_APPROVAL, [], "2026-11-01T08:00:00+00:00"),
        ("2026-11-01-d", Status.AWAITING_APPROVAL, [], "2026-11-01T07:00:00+00:00"),
    ]
    for run_id, status, finished, created in on_disk:
        manifest = Manifest(
            run_id, "q", personal=True, status=status, finished_phases=finished, created_at=created
        )
        manifest.phase = Phase.ANALYSE if finished else Phase.PLAN
        manifest.plan_text = "" if run_id.endswith("-d") else "PLAN"  # d's draft was cut off
        write_manifest(create_run_dir(config.private_root, run_id), manifest)

    daemon = await start_daemon(config, phases.backend())
    try:
        await wait_until(lambda: len(phases.started) == 2)
        # Created order, and each resumes from its own finished phases.
        assert phases.started == [("2026-11-01-a", ["plan", "collect"]), ("2026-11-01-b", [])]
        assert daemon.chamber.status("2026-11-01-c")["status"] == "awaiting_approval"
        # An ask that saves while shutdown unwinds run a must not save phases' CANCELLED.
        phases.unwind_s = 0.2
        ask = asyncio.create_task(daemon.chamber.ask("2026-11-01-a", "mid-run?"))
        await asyncio.sleep(0.01)
    finally:
        await daemon.close()
    assert (await ask)["answer"] == "ANSWER: mid-run?"
    # A shutdown is not a cancel, even though phases records CANCELLED on any cancel:
    # the runs stay running in memory and on disk for the next start.
    assert [row["status"] for row in daemon.chamber.list_runs()["runs"]] == [
        "failed",
        "awaiting_approval",
        "running",
        "running",
    ]
    for run_id in ("2026-11-01-a", "2026-11-01-b"):
        assert read_manifest(config.private_root / run_id).status is Status.RUNNING
    assert phases.closed == []

    phases.unwind_s = 0.0
    again = await start_daemon(config, phases.backend())  # close() freed the lock
    try:
        await wait_until(lambda: len(phases.started) == 4)
    finally:
        await again.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_unwind", [False, True])
async def test_cancel_is_recorded_and_announced_once(
    daemon, phases, config, monkeypatch, wait_until, slow_unwind: bool
) -> None:
    """Cancel in the same tick as approve, or with an unwind that outlasts the /cancel wait."""
    chamber = daemon.chamber
    run_id = (await chamber.start("q"))["run_id"]
    await chamber.approve(run_id, None, True)
    if slow_unwind:
        monkeypatch.setattr("analysis_chamber.daemon.engine.chamber.CANCEL_WAIT_S", 0.01)
        phases.stall_s = 0.2
        await wait_until(lambda: phases.started)
    reply = await chamber.cancel(run_id)
    manifest_path = config.private_root / run_id / "manifest.json"
    written_ns = manifest_path.stat().st_mtime_ns
    task_name = f"run-{run_id}"  # the Scheduler's task name
    await wait_until(lambda: all(t.get_name() != task_name for t in asyncio.all_tasks()))

    assert reply["status"] == "cancelled" and phases.closed == [run_id]
    assert read_manifest(manifest_path.parent).status is Status.CANCELLED
    assert manifest_path.stat().st_mtime_ns == written_ns


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["too long", "in the repo"])
async def test_bad_private_root_is_refused_with_no_folder(config, phases, where: str) -> None:
    if where == "too long":
        private_root = config.private_root / ("x" * 100)
    else:
        private_root = config.repo_root / "private"
    chamber = Chamber(replace(config, private_root=private_root), phases.backend())
    with pytest.raises((ChamberError, LeakError)):
        await chamber.start("q")
    assert not private_root.exists() and chamber.list_runs()["runs"] == []


# (personal, report fields from the run, publish offered?)
LEAK_TABLE = [
    (True, {"report_format": "artifact", "outputs": {"report": "report.html"}}, False),
    (False, {"report_format": "artifact", "outputs": {"report": "report.html"}}, True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("personal", "report", "publish"), LEAK_TABLE)
async def test_run_location_and_publish_offer(
    daemon, client, phases, config, wait_until, personal: bool, report: dict, publish: bool
) -> None:
    phases.report.update(report)
    run_id = (await call(client, "start", "my inbox habits"))["run_id"]
    await call(client, "approve", run_id, personal=personal)
    phases.gate.set()
    await wait_until(lambda: daemon.chamber.status(run_id)["status"] == "done")

    status = await call(client, "status", run_id)
    run_dir = config.private_root / run_id if personal else config.analyses_root / run_id
    assert status["run_dir"] == str(run_dir) and (run_dir / "manifest.json").exists()
    assert is_under(run_dir, config.repo_root) is not personal
    assert ("publish" in status) is publish
    if publish:
        assert status["publish"] == {"html_path": str(run_dir / "report.html")}


@pytest.mark.asyncio
async def test_failed_move_leaves_the_run_private_and_unapproved(
    daemon, client, config, monkeypatch
) -> None:
    run_id = (await call(client, "start", "rent prices"))["run_id"]

    def refuse_rename(self, target):
        raise OSError("disk said no")

    monkeypatch.setattr(Path, "rename", refuse_rename)
    with pytest.raises(DaemonError, match="couldn't move run"):
        await call(client, "approve", run_id, personal=False)

    status = await call(client, "status", run_id)
    assert status["status"] == "awaiting_approval" and status["personal"] is None
    assert status["run_dir"] == str(config.private_root / run_id)
    assert not (config.analyses_root / run_id).exists()


@pytest.mark.asyncio
async def test_concurrent_asks_on_one_run_take_turns(daemon, client, phases) -> None:
    run_id = (await call(client, "start", "rent prices"))["run_id"]
    answers = await asyncio.gather(
        call(client, "ask", run_id, "one?"), call(client, "ask", run_id, "two?")
    )
    assert sorted(reply["answer"] for reply in answers) == ["ANSWER: one?", "ANSWER: two?"]
    assert phases.asks_peak == 1


@pytest.mark.asyncio
async def test_cut_off_plan_draft_fails_the_run(config, phases) -> None:
    drafting = asyncio.Event()

    async def blocking_draft(ctx, agents) -> str:
        drafting.set()
        await asyncio.Event().wait()  # never answers
        return "unreachable"

    phases.draft_plan = blocking_draft
    chamber = Chamber(config, phases.backend())
    start = asyncio.create_task(chamber.start("q"))
    await drafting.wait()
    start.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start

    (run,) = chamber.list_runs()["runs"]
    manifest = read_manifest(config.private_root / run["run_id"])
    assert manifest.status is Status.FAILED and manifest.last_error == "plan draft interrupted"
