"""Backend: the agent-side pieces the daemon drives, injected so tests can fake them.

The daemon itself only moves runs between states and folders. Everything that
runs an agent turn (plan, revise, pipeline, Q&A) comes in
through this record. `wiring.default_backend` builds the real one; tests pass
fakes with the same call shapes.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analysis_chamber.config import ChamberConfig
from analysis_chamber.runs import Manifest

# (run_dir, manifest, config) -> a RunContext (or a fake with the same fields).
MakeContext = Callable[[Path, Manifest, ChamberConfig], Any]
OnUpdate = Callable[[Manifest], Awaitable[None]]


@dataclass(frozen=True)
class Backend:
    """The phase functions plus the shared objects they're called with.

    Attributes:
        agents: phases.PhaseAgents (runner plus option builders), passed through untouched.
        notifier: Notifier; the daemon awaits `progress` in on_update and `closed`
            once per failed or cancelled run.
        make_context: Builds the RunContext for a run.
        make_hooks: (on_update, notifier) -> phases.PipelineHooks (notifier, on_update, kit).
            The daemon passes a per-run notifier that sends one closed notice per run.
        draft_plan: async (ctx, agents) -> plan text.
        revise_plan: async (ctx, agents, edits) -> plan text.
        run_pipeline: async (ctx, agents, hooks) -> None; builds the run venv itself.
        ask: async (ctx, agents, question) -> answer text.
    """

    agents: Any
    notifier: Any
    make_context: MakeContext
    make_hooks: Callable[[OnUpdate, Any], Any]
    draft_plan: Callable[..., Awaitable[str]]
    revise_plan: Callable[..., Awaitable[str]]
    run_pipeline: Callable[..., Awaitable[None]]
    ask: Callable[..., Awaitable[str]]
