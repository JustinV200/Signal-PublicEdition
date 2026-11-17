"""ask: Q&A over a run folder, mid-run or after it's done, logged to qa.md.

Per the session-resume spike, a Q&A turn forks the lead session
(fork_session=True), which gives it the lead's full context without writing into
the lead's transcript, and is safe while the lead is mid-turn. After the run is
done, the first fork's id is stored as manifest.sessions["qa"] and resumed for
later questions. Mid-run forks are never stored. With no usable lead session,
a fresh Q&A session reads the folder instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analysis_chamber.phases.deps import PhaseAgents
from analysis_chamber.phases.prompts import render
from analysis_chamber.phases.turns import (
    LEAD_ROLE,
    SessionTurn,
    checked,
    remember_session,
    session_turn,
    stored_session,
    try_resume,
)
from analysis_chamber.runs import Status, utc_now_iso

if TYPE_CHECKING:
    from analysis_chamber.agents import RunContext

QA_ROLE = "qa"
QA_FILE = "qa.md"


async def ask(ctx: RunContext, agents: PhaseAgents, question: str) -> str:
    """Answer a question about the run and append it to qa.md.

    An answer given before the run is done starts with a partial-results flag.
    May store manifest.sessions["qa"]; the caller persists the manifest.

    Returns:
        The answer text.

    Raises:
        PhaseError: The Q&A turn failed.
    """
    manifest = ctx.manifest
    if manifest.status is Status.DONE:
        answer = await _ask_done(ctx, agents, question)
    else:
        note = (
            f"The run isn't finished (phase {manifest.phase.value}, status "
            f"{manifest.status.value}): say what your answer rests on."
        )
        answer = await _forked_turn(ctx, agents, _first_prompt(ctx, question, note), store=False)
        answer = (
            f"Based on partial results (run not finished, phase {manifest.phase.value}): {answer}"
        )
    _append_qa(ctx, question, answer)
    return answer


async def _ask_done(ctx: RunContext, agents: PhaseAgents, question: str) -> str:
    """Resume the stored Q&A session, or fork the lead to start one."""
    if not stored_session(ctx.manifest, QA_ROLE, ctx.run_dir):
        prompt = _first_prompt(ctx, question, "The run is finished.")
        return await _forked_turn(ctx, agents, prompt, store=True)
    turn = SessionTurn(
        role=QA_ROLE,
        prompt=question,
        fresh_prefix=render("qa", run_dir=ctx.run_dir, status_note="The run is finished."),
        make_options=lambda resume: agents.options.qa(ctx, resume, fork=False),
    )
    return await session_turn(ctx, agents.runner, turn)


async def _forked_turn(ctx: RunContext, agents: PhaseAgents, prompt: str, store: bool) -> str:
    """A Q&A turn in a fork of the lead session, or a fresh session if that can't work."""
    lead = stored_session(ctx.manifest, LEAD_ROLE, ctx.run_dir)
    result = None
    if lead:
        options = agents.options.qa(ctx, lead, fork=True)
        result = await try_resume(agents.runner, options, prompt, lead)
    if result is None:
        options = agents.options.qa(ctx, None, fork=False)
        result = checked(await agents.runner.run(options, prompt), "Q&A turn")
    if store:
        remember_session(ctx.manifest, QA_ROLE, result.session_id, ctx.run_dir)
    return result.text


def _first_prompt(ctx: RunContext, question: str, status_note: str) -> str:
    """The Q&A guidance plus the question, for a session's first turn."""
    guidance = render("qa", run_dir=ctx.run_dir, status_note=status_note)
    return f"{guidance}\n\nQuestion: {question}"


def _append_qa(ctx: RunContext, question: str, answer: str) -> None:
    """Append one Q and A, with a timestamp, to qa.md."""
    path = ctx.run_dir / QA_FILE
    entry = f"## {utc_now_iso()}\n\n**Q:** {question.strip()}\n\n**A:** {answer.strip()}\n\n"
    with path.open("a", encoding="utf-8") as file:
        if path.stat().st_size == 0:
            file.write("# Q&A\n\n")
        file.write(entry)
