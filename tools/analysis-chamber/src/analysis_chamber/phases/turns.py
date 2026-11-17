"""One agent turn with session resume, and the fresh-session fallback when resume can't be used.

Session-resume spike (notes not published):
- A session must be resumed with the cwd it was made in, or its tools silently run
  in the wrong folder. Each stored session id has its cwd next to it in
  manifest.sessions (`<role>_cwd`); a session from another folder (a run moved
  from private_root at approval) is never resumed.
- If resume isn't possible or returns an error, the turn re-runs in a fresh
  session that first gets a summary of the run folder, so the phase restarts from
  its on-disk checkpoint. The new session id replaces the old.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from analysis_chamber.phases.deps import PhaseAgents, PhaseError
from analysis_chamber.phases.prompts import render
from analysis_chamber.runs import Manifest

if TYPE_CHECKING:
    from analysis_chamber.agents import AgentRunner, RunContext, TurnResult

log = logging.getLogger(__name__)

LEAD_ROLE = "lead"
CWD_SUFFIX = "_cwd"
ERROR_EXCERPT_CHARS = 500
# Big or noisy folders the summary lists by count only, never file by file.
_COUNT_ONLY_DIRS = {"data", "models", "extracts"}
_SKIPPED_DIRS = {".venv", "__pycache__", ".ipynb_checkpoints"}


@dataclass(frozen=True)
class SessionTurn:
    """One turn for a stored-session role.

    Attributes:
        role: Key in manifest.sessions ("lead", "qa").
        prompt: What to say this turn.
        fresh_prefix: Guidance a brand-new session needs before the prompt.
        make_options: Builds SDK options given the session id being resumed (or None).
    """

    role: str
    prompt: str
    fresh_prefix: str
    make_options: Callable[[str | None], Any]


def stored_session(manifest: Manifest, role: str, run_dir: Path) -> str | None:
    """The role's session id, but only if it was made in run_dir (else None)."""
    session_id = manifest.sessions.get(role)
    cwd = manifest.sessions.get(role + CWD_SUFFIX)
    if not session_id or not cwd or os.path.normcase(cwd) != os.path.normcase(str(run_dir)):
        return None
    return session_id


def remember_session(manifest: Manifest, role: str, session_id: str, run_dir: Path) -> None:
    """Store the role's session id with the cwd it runs in."""
    manifest.sessions[role] = session_id
    manifest.sessions[role + CWD_SUFFIX] = str(run_dir)


def checked(result: TurnResult, what: str) -> TurnResult:
    """The result, or PhaseError if the turn failed."""
    if result.is_error:
        raise PhaseError(f"{what} failed: {result.text[:ERROR_EXCERPT_CHARS]}")
    return result


async def try_resume(
    runner: AgentRunner, options: Any, prompt: str, resume: str
) -> TurnResult | None:
    """Run a resume (or fork) turn; None if it failed, so the caller starts fresh.

    A refused resume raises from the SDK (ClaudeSDKError / ProcessError at
    initialize) rather than returning is_error, so both count as failure here.
    CancelledError is a BaseException and still propagates.
    """
    try:
        result = await runner.run(options, prompt, resume=resume)
    except Exception as error:
        log.warning("resuming session %s raised, starting fresh: %r", resume, error)
        return None
    if result.is_error:
        log.warning(
            "resuming session %s failed, starting fresh: %s",
            resume,
            result.text[:ERROR_EXCERPT_CHARS],
        )
        return None
    return result


async def session_turn(ctx: RunContext, runner: AgentRunner, turn: SessionTurn) -> str:
    """Run the turn, resuming the role's stored session when that's safe.

    Returns:
        The agent's reply text.

    Raises:
        PhaseError: The fresh-session turn failed too.
    """
    resume = stored_session(ctx.manifest, turn.role, ctx.run_dir)
    if resume:
        options = turn.make_options(resume)
        result = await try_resume(runner, options, turn.prompt, resume)
        if result is not None:
            remember_session(ctx.manifest, turn.role, result.session_id, ctx.run_dir)
            return result.text
    prefix = turn.fresh_prefix
    if ctx.manifest.sessions.get(turn.role):
        # There was a session, but it's gone or from another folder: seed from disk.
        prefix = f"{prefix}\n\n{run_summary(ctx)}"
    result = await runner.run(turn.make_options(None), f"{prefix}\n\n{turn.prompt}")
    checked(result, f"{turn.role} turn")
    remember_session(ctx.manifest, turn.role, result.session_id, ctx.run_dir)
    return result.text


async def lead_turn(
    ctx: RunContext, agents: PhaseAgents, prompt: str, plan_only: bool = False
) -> str:
    """A lead turn: resume the lead session, or start one with the lead guidance.

    plan_only uses the plan options (no MCP servers), for plan and revise turns.
    """
    build = agents.options.plan if plan_only else agents.options.lead
    turn = SessionTurn(
        role=LEAD_ROLE,
        prompt=prompt,
        fresh_prefix=lead_guidance(ctx),
        make_options=lambda _resume: build(ctx),
    )
    return await session_turn(ctx, agents.runner, turn)


def lead_guidance(ctx: RunContext) -> str:
    """The lead's standing rules (playbook, no raw pages, layout, markers)."""
    return render("lead", run_dir=ctx.run_dir, playbook=ctx.config.playbook_path)


def run_summary(ctx: RunContext) -> str:
    """What a fresh session needs to pick up the run: question, plan, progress, files."""
    manifest = ctx.manifest
    return render(
        "resume",
        question=manifest.question,
        finished=", ".join(manifest.finished_phases) or "none",
        plan=manifest.plan_text or "(no plan yet)",
        files=_list_files(ctx.run_dir),
    )


def _list_files(run_dir: Path) -> str:
    """A short listing: top-level files, code/figures by name, big folders by count."""
    lines: list[str] = []
    for entry in sorted(run_dir.iterdir()):
        if entry.name in _SKIPPED_DIRS:
            continue
        if entry.is_file():
            lines.append(f"- {entry.name}")
        elif entry.name in _COUNT_ONLY_DIRS:
            count = sum(1 for path in entry.rglob("*") if path.is_file())
            lines.append(f"- {entry.name}/ ({count} files)")
        else:
            names = sorted(path.name for path in entry.iterdir() if path.is_file())
            lines.append(f"- {entry.name}/: {', '.join(names) or '(empty)'}")
    return "\n".join(lines)
