"""default_backend: the real Backend, built from the agents, phases, kit and notify packages.

This is the one place the daemon touches those packages. The imports sit inside
the function so the rest of the daemon (and its tests, which pass a fake
Backend) never load the Agent SDK.
"""

from types import SimpleNamespace

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.backend import Backend, OnUpdate


def default_backend(config: ChamberConfig) -> Backend:
    """Wire the real phase functions, SDK runner, option builders, kit and notifier.

    Args:
        config: Chamber config (the notifier needs repo_root).

    Returns:
        The Backend `serve` runs with.
    """
    from analysis_chamber import kit, phases
    from analysis_chamber.agents import (
        RunContext,
        SdkRunner,
        collect_tools_text,
        critic_options,
        lead_options,
        plan_options,
        qa_options,
    )
    from analysis_chamber.notify import Notifier

    notifier = Notifier(config)
    # phases.AgentOptionsFactory asks for exactly this namespace (phases/deps.py).
    options = SimpleNamespace(
        plan=plan_options,
        lead=lead_options,
        critic=critic_options,
        qa=qa_options,
        collect_tools=collect_tools_text,
    )

    def make_hooks(on_update: OnUpdate, run_notifier: object) -> object:
        return phases.PipelineHooks(notifier=run_notifier, on_update=on_update, kit=kit)

    return Backend(
        agents=phases.PhaseAgents(runner=SdkRunner(), options=options),
        notifier=notifier,
        make_context=RunContext,
        make_hooks=make_hooks,
        draft_plan=phases.draft_plan,
        revise_plan=phases.revise_plan,
        run_pipeline=phases.run_pipeline,
        ask=phases.ask,
    )
