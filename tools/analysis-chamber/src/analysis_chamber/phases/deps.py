"""What the phases need from the rest of the chamber, as small injectable bundles.

The daemon builds these from the real agents, kit and notify packages; tests pass
fakes. Phases only call methods on them, so agents/notify are imported for type
checking only.

Persistence rule: phases mutate `ctx.manifest` in place. run_pipeline awaits
`PipelineHooks.on_update(manifest)` on every phase or percent change and at the
end; the daemon's on_update persists it (write_manifest) and awaits
notifier.progress. run_pipeline itself only awaits notifier.done and
notifier.closed. draft_plan, revise_plan and ask don't get hooks: the caller
persists after they return.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from analysis_chamber.config import ChamberConfig
from analysis_chamber.runs import Manifest

if TYPE_CHECKING:
    from analysis_chamber.agents import AgentRunner, RunContext
    from analysis_chamber.notify import Notifier


class PhaseError(RuntimeError):
    """An agent turn failed, or a phase didn't produce what it must."""


class AgentOptionsFactory(Protocol):
    """Builds SDK options per role. The daemon passes
    `SimpleNamespace(lead=lead_options, plan=plan_options, critic=critic_options,
    qa=qa_options, collect_tools=collect_tools_text)`."""

    def lead(self, ctx: RunContext) -> Any: ...

    def plan(self, ctx: RunContext) -> Any:
        """The lead's options with no MCP servers, so a plan turn can't collect."""
        ...

    def collect_tools(self, ctx: RunContext) -> str:
        """Markdown list of what the collect phase can use, for the plan prompt."""
        ...

    def critic(self, ctx: RunContext) -> Any: ...

    def qa(self, ctx: RunContext, resume: str | None, fork: bool) -> Any:
        """Q&A options; fork=True means fork session `resume` (fork_session=True)."""
        ...


class RunKit(Protocol):
    """The kit calls the pipeline makes (blocking; run via asyncio.to_thread).

    The `analysis_chamber.kit` module fits as-is. make_run_venv must be idempotent.
    """

    def make_run_venv(self, run_dir: Path, config: ChamberConfig) -> Path: ...

    def list_installs(self, run_dir: Path, config: ChamberConfig) -> list[dict]: ...


@dataclass(frozen=True)
class PhaseAgents:
    """The runner that executes turns and the options builder for each role."""

    runner: AgentRunner
    options: AgentOptionsFactory


@dataclass(frozen=True)
class PipelineHooks:
    """Side effects run_pipeline triggers: persistence, notifications and the run venv.

    Attributes:
        notifier: Awaited for done / closed (progress goes through on_update).
        on_update: Awaited with ctx.manifest on every change; persists and reports progress.
        kit: Run venv creation and install listing.
    """

    notifier: Notifier
    on_update: Callable[[Manifest], Awaitable[None]]
    kit: RunKit


@dataclass(frozen=True)
class StepCall:
    """What run_pipeline hands each phase step.

    Attributes:
        intro: Text to put before the step's first lead prompt ("" normally; a note
            that the phase was interrupted when it's being re-run after a crash).
        progress: Awaited with the fraction (0-1) of the phase done, for steps that
            can tell (critique rounds).
    """

    intro: str
    progress: Callable[[float], Awaitable[None]]
