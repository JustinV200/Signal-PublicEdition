"""Fixtures for the daemon tests: a temp config and a fake Backend (no SDK, no agents)."""

import asyncio
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

from analysis_chamber.config import load_config
from analysis_chamber.daemon import Backend, DaemonClient, start_daemon
from analysis_chamber.runs import Status


@dataclass
class FakePhases:
    """Fake phase functions with the real phases contract (phases/pipeline.py).

    run_pipeline waits on `gate`, then marks the run done through on_update. On a
    cancel it does what the real one does: sets CANCELLED, awaits on_update and
    notifier.closed, then re-raises (with `stall_s` and `unwind_s` pauses).
    ask records how many asks overlap.

    Attributes:
        gate: Set it to let every waiting pipeline finish.
        started: (run id, finished_phases at start) per pipeline call, in order.
        closed: Run ids the notifier was told were closed.
        report: Fields the fake report phase sets on the manifest.
        asks_live, asks_peak: Asks running now, and the most at once.
        stall_s: How long a cancelled pipeline takes to start recording CANCELLED.
        unwind_s: How long it takes between saving CANCELLED and closed.
    """

    gate: asyncio.Event = field(default_factory=asyncio.Event)
    started: list[tuple[str, list[str]]] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)
    asks_live: int = 0
    asks_peak: int = 0
    stall_s: float = 0.0
    unwind_s: float = 0.0

    async def draft_plan(self, ctx, agents) -> str:
        return f"PLAN: {ctx.manifest.question}"

    async def revise_plan(self, ctx, agents, edits: str) -> str:
        return f"REVISED: {edits}"

    async def ask(self, ctx, agents, question: str) -> str:
        self.asks_live += 1
        self.asks_peak = max(self.asks_peak, self.asks_live)
        await asyncio.sleep(0.05)
        self.asks_live -= 1
        return f"ANSWER: {question}"

    async def run_pipeline(self, ctx, agents, hooks) -> None:
        manifest = ctx.manifest
        self.started.append((manifest.id, list(manifest.finished_phases)))
        manifest.status = Status.RUNNING
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            await asyncio.sleep(self.stall_s)
            manifest.status = Status.CANCELLED
            await hooks.on_update(manifest)
            await asyncio.sleep(self.unwind_s)
            await hooks.notifier.closed(manifest)
            raise
        for key, value in self.report.items():
            setattr(manifest, key, value)
        manifest.status, manifest.percent = Status.DONE, 100
        await hooks.on_update(manifest)

    def backend(self) -> Backend:
        async def progress(manifest) -> None:
            return None

        async def closed(manifest) -> None:
            self.closed.append(manifest.id)

        notifier = SimpleNamespace(progress=progress, closed=closed)
        return Backend(
            agents=None,
            notifier=notifier,
            make_context=lambda run_dir, manifest, config: SimpleNamespace(
                run_dir=run_dir, manifest=manifest, config=config
            ),
            make_hooks=lambda on_update, run_notifier: SimpleNamespace(
                notifier=run_notifier, on_update=on_update
            ),
            draft_plan=self.draft_plan,
            revise_plan=self.revise_plan,
            run_pipeline=self.run_pipeline,
            ask=self.ask,
        )


@pytest.fixture
def config():
    # Not tmp_path: its long name would break the daemon's 100-character run folder limit.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as short_dir:
        base = Path(short_dir)
        repo = base / "Signal"
        yield replace(
            load_config(base / "missing.toml"),
            repo_root=repo,
            analyses_root=repo / "life" / "analyses",
            private_root=base / "priv",
            state_dir=base / "state",
            log_dir=base / "logs",
        )


async def _wait_until(predicate, timeout_s: float = 5.0) -> None:
    """Poll until predicate() holds (the daemon's run tasks share this loop)."""
    async with asyncio.timeout(timeout_s):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.fixture
def wait_until():
    """The polling helper, as a fixture so test files needn't import conftest."""
    return _wait_until


@pytest.fixture
def phases() -> FakePhases:
    return FakePhases()


@pytest_asyncio.fixture
async def daemon(config, phases):
    running = await start_daemon(config, phases.backend())
    yield running
    phases.gate.set()
    await running.close()


@pytest.fixture
def client(config) -> DaemonClient:
    return DaemonClient(config.state_dir)
