"""Fakes for testing analysis_chamber.phases: a scripted runner, options, notifier and kit.

FakeContext and FakeTurn mirror agents.RunContext and agents.TurnResult, so these
tests don't depend on the agents package (phases only reads their attributes).
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from analysis_chamber.config import ChamberConfig, load_config
from analysis_chamber.phases import PhaseAgents, PipelineHooks
from analysis_chamber.runs import Manifest, create_run_dir


@dataclass
class FakeContext:
    """Same fields as agents.RunContext."""

    run_dir: Path
    manifest: Manifest
    config: ChamberConfig


@dataclass(frozen=True)
class FakeTurn:
    """Same fields as agents.TurnResult."""

    session_id: str
    text: str
    is_error: bool


@dataclass
class Call:
    """One runner.run call as the fake saw it."""

    options: tuple
    prompt: str
    resume: str | None


@dataclass
class FakeRunner:
    """Records calls; `reply(call, run_dir)` returns the FakeTurn (may write files)."""

    run_dir: Path
    reply: Callable[[Call, Path], FakeTurn]
    calls: list[Call] = field(default_factory=list)

    async def run(self, options, prompt, resume=None):
        call = Call(options, prompt, resume)
        self.calls.append(call)
        return self.reply(call, self.run_dir)


class FakeOptions:
    """Options are just tuples naming the role, so tests can see which was used."""

    def lead(self, ctx):
        return ("lead",)

    def plan(self, ctx):
        return ("plan",)

    def collect_tools(self, ctx):
        return "- FAKE-TOOL-LIST"

    def critic(self, ctx):
        return ("critic",)

    def qa(self, ctx, resume, fork):
        return ("qa", resume, fork)


@dataclass
class FakeNotifier:
    """Records done/closed notifications (phases never call progress)."""

    done_calls: list[tuple] = field(default_factory=list)
    closed_calls: int = 0

    async def done(self, manifest, top_finding, report_path):
        self.done_calls.append((top_finding, report_path))

    async def closed(self, manifest):
        self.closed_calls += 1


class FakeKit:
    """No real venvs: make_run_venv just makes the folder."""

    def make_run_venv(self, run_dir, config):
        (run_dir / ".venv").mkdir(exist_ok=True)
        return run_dir / ".venv"

    def list_installs(self, run_dir, config):
        return [{"package": "ruptures", "version": "1.1.9"}]


def make_ctx(tmp_path: Path, **manifest_fields) -> FakeContext:
    """A run folder under tmp_path with a manifest built from manifest_fields."""
    config = replace(
        load_config(tmp_path / "missing.toml"),
        analyses_root=tmp_path / "analyses",
        private_root=tmp_path / "private",
        critic_rounds_max=2,
    )
    manifest = Manifest(id="2026-11-16-q", question="What moves X?", **manifest_fields)
    run_dir = create_run_dir(config.private_root, manifest.id)
    return FakeContext(run_dir=run_dir, manifest=manifest, config=config)


def ok(text: str = "ok", session_id: str = "s1") -> FakeTurn:
    """A successful turn."""
    return FakeTurn(session_id=session_id, text=text, is_error=False)


def failed(text: str = "boom") -> FakeTurn:
    """A failed turn."""
    return FakeTurn(session_id="", text=text, is_error=True)


def wire(ctx: FakeContext, reply: Callable[[Call, Path], FakeTurn]):
    """Fake agents, hooks and their recorders for one run."""
    runner = FakeRunner(ctx.run_dir, reply)
    notifier = FakeNotifier()

    async def on_update(manifest):
        pass

    agents = PhaseAgents(runner=runner, options=FakeOptions())
    hooks = PipelineHooks(notifier=notifier, on_update=on_update, kit=FakeKit())
    return agents, hooks, runner, notifier
