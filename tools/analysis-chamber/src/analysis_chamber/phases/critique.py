"""The critique phase: fresh critic rounds, lead fixes, everything recorded in critique.md.

Each round starts a new critic session (never resumed, so it shares no context
with the lead or earlier critics). critique.md is written by this code, not the
lead, so every round's findings and resolutions are always on disk before the
next critic reads the folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from analysis_chamber.phases.deps import PhaseAgents, StepCall
from analysis_chamber.phases.markers import has_flag
from analysis_chamber.phases.prompts import render
from analysis_chamber.phases.turns import checked, lead_turn

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

CRITIQUE_FILE = "critique.md"
NO_FINDINGS = "NO_FINDINGS"


async def run_critique(ctx: RunContext, agents: PhaseAgents, call: StepCall) -> None:
    """Up to config.critic_rounds_max critic rounds; stops early when a critic finds nothing.

    Args:
        ctx: The run.
        agents: Runner and options.
        call: call.progress is awaited with the fraction of rounds done after each
            round. call.intro is unused: an interrupted critique restarts its rounds.

    Raises:
        PhaseError: A critic or lead turn failed.
    """
    rounds_max = ctx.config.critic_rounds_max
    path = ctx.run_dir / CRITIQUE_FILE
    # A rerun after a crash starts the record over, matching the restarted rounds.
    path.write_text("# Critique\n", encoding="utf-8")
    for round_number in range(1, rounds_max + 1):
        findings = await _critic_round(ctx, agents, round_number)
        if has_flag(findings, NO_FINDINGS):
            _append(path, round_number, "Critic found nothing that needs fixing.")
            await call.progress(1.0)
            return
        prompt = render("critic_fix", round=round_number, findings=findings)
        resolutions = await lead_turn(ctx, agents, prompt)
        _append(
            path,
            round_number,
            f"### Critic findings\n\n{findings}\n\n### Resolutions\n\n{resolutions}",
        )
        await call.progress(round_number / rounds_max)


async def _critic_round(ctx: RunContext, agents: PhaseAgents, round_number: int) -> str:
    """One fresh critic session's findings text."""
    prompt = render(
        "critic",
        run_dir=ctx.run_dir,
        playbook=ctx.config.playbook_path,
        round=round_number,
        rounds_max=ctx.config.critic_rounds_max,
    )
    result = await agents.runner.run(agents.options.critic(ctx), prompt, resume=None)
    return checked(result, f"critic round {round_number}").text.strip()


def _append(path: Path, round_number: int, body: str) -> None:
    """Add one round's section to critique.md."""
    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n## Round {round_number}\n\n{body.strip()}\n")
