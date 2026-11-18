"""The plan phase: the lead drafts (and on edits revises) the plan; nothing is collected.

Plan turns use the plan options (the lead with no MCP servers), so they can't
fetch or read Signal data before approval. The prompt lists what the collect phase
can use (generated from the real config), so the plan only names available sources.

The personal-flag section is added here, not by the lead, so it always says
the user must choose and names both storage locations (spec 7.1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analysis_chamber.phases.deps import PhaseAgents
from analysis_chamber.phases.prompts import render
from analysis_chamber.phases.turns import lead_turn

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

PLAN_FILE = "plan.md"


async def draft_plan(ctx: RunContext, agents: PhaseAgents) -> str:
    """Have the lead draft the plan; write plan.md and set manifest.plan_text.

    Stores the lead session id in manifest.sessions["lead"]. The caller persists
    the manifest.

    Returns:
        The full plan text.

    Raises:
        PhaseError: The lead turn failed.
    """
    tools = agents.options.collect_tools(ctx)
    prompt = render("plan", question=ctx.manifest.question, tools=tools)
    reply = await lead_turn(ctx, agents, prompt, plan_only=True)
    return _save_plan(ctx, reply)


async def revise_plan(ctx: RunContext, agents: PhaseAgents, edits: str) -> str:
    """Resume the lead with the user's edits; rewrite plan.md and manifest.plan_text.

    Returns:
        The full revised plan text.

    Raises:
        PhaseError: The lead turn failed.
    """
    reply = await lead_turn(ctx, agents, render("revise", edits=edits), plan_only=True)
    return _save_plan(ctx, reply)


def _save_plan(ctx: RunContext, reply: str) -> str:
    """Append the personal section to the lead's plan, then store it."""
    config, run_id = ctx.config, ctx.manifest.id
    personal = (
        "## Personal\n\n"
        "The user must choose personal = yes or no (the lead doesn't suggest one).\n"
        f"- yes: the run stays in {config.private_root / run_id}, never committed or published.\n"
        f"- no: the run moves to {config.analyses_root}, renamed to a readable id."
    )
    plan = f"{reply.strip()}\n\n{personal}\n"
    (ctx.run_dir / PLAN_FILE).write_text(plan, encoding="utf-8")
    ctx.manifest.plan_text = plan
    return plan
