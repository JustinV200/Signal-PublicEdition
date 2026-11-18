"""`setup auto [tools]`: run the automatic steps of the picked tools in one go, asking nothing.

The setup window's `Save picks and install` and each tool's `Run the automatic steps`
call this, so the owner clicks once instead of once per install. A step is automatic when
`Step.is_automatic` says so: a required run or copy step that isn't a terminal step or a
browser sign-in. Each picked tool's steps go in registry order:

- done or skipped steps are passed over, and so are optional ones: they register
  scheduled tasks or build Docker images, so each waits for its own click;
- the first required step that needs the owner (or fails) ends that tool, since its later
  steps build on it, and the batch carries on with the next tool.

Only picked tools run (an id that isn't picked is said and passed over). It writes
progress only, never Claude Code's config. Prints each step's live output, then one JSON
object: `{"ran": [...], "stopped": [...], "messages": [...]}`.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from signal_setup import platforms, progress, registry
from signal_setup.registry import Tool
from signal_setup.steps import NEEDS_INPUT, run_step

NEEDS_YOU = "needs_you"
# Exit codes, as `setup apply` gives them: 1 a step failed, 2 none of the named tools can
# run here (unknown, not picked or not for this OS: main gives 2 for an unknown id too),
# 3 a step needs the owner.
EXIT_FAILED, EXIT_NONE_USABLE, EXIT_NEEDS_YOU = 1, 2, 3
ALL_DONE = "Every required step of your picks is done; optional steps wait for your click."
NONE_USABLE = "Nothing ran: none of the named tools is picked and can run on this OS."
NOTHING_PICKED = "Nothing ran: nothing is picked yet."


@dataclass(frozen=True)
class Stop:
    """Where one tool's run ended early: the step, and why (NEEDS_YOU or progress.FAILED)."""

    tool: str
    step: str
    title: str
    reason: str


class _LogAsker:
    """Prints what a step says, as it says it; has no answers (run and copy ask nothing)."""

    interactive = False

    def say(self, text: str) -> None:
        """Print the line now, so it shows live in the setup window's log."""
        print(text, flush=True)

    def confirm(self, question: str, default: bool) -> None:
        """No answer: an automatic step never asks."""
        return None

    def text(self, question: str) -> None:
        """No answer: an automatic step never asks."""
        return None


def _run_tool(root: Path, tool: Tool, ran: list[dict[str, str]]) -> Stop | None:
    """Run `tool`'s automatic steps in order; the Stop where it ended early, or None."""
    for step in progress.applicable_steps(tool, platforms.current()):
        status = progress.step_status(progress.load(root), tool.id, step.id)
        if step.optional or status in (progress.DONE, progress.SKIPPED):
            continue
        if not step.is_automatic():
            return Stop(tool.id, step.id, step.title, NEEDS_YOU)
        print(f"\n== {tool.name}: {step.title} ==", flush=True)
        # Run on a copy, then save only this step's status onto the progress as it is now:
        # an install takes minutes, and a terminal's `setup step` may save meanwhile.
        status = run_step(root, tool, step, progress.load(root), _LogAsker())
        if status != NEEDS_INPUT:
            fresh = progress.load(root)
            progress.set_step(fresh, tool.id, step.id, status)
            progress.save(root, fresh)
        ran.append({"tool": tool.id, "step": step.id, "status": status})
        if status != progress.DONE:
            reason = progress.FAILED if status == progress.FAILED else NEEDS_YOU
            return Stop(tool.id, step.id, step.title, reason)
    return None


def _picked_tools(root: Path, tool_ids: list[str]) -> list[Tool]:
    """The tools to run, in registry order: the picks (or those of `tool_ids` that are picks).

    Raises:
        KeyError: An unknown tool id (main turns it into exit 2).
    """
    asked = {registry.by_id(i).id for i in tool_ids}
    chosen, platform = progress.load(root)["chosen"], platforms.current()
    tools = []
    for tool in registry.load():
        if asked and tool.id not in asked:
            continue
        if tool.id not in chosen:
            if asked:
                print(f"{tool.name} isn't picked, so nothing of it runs.", flush=True)
        elif not platforms.is_supported(tool, platform):
            print(f"{tool.name} can't run on this OS, so nothing of it runs.", flush=True)
        else:
            tools.append(tool)
    return tools


def _stop_words(stop: Stop) -> str:
    """One stop in words, naming the tool and the step."""
    name = registry.by_id(stop.tool).name
    if stop.reason == progress.FAILED:
        return f"Failed: {name}, '{stop.title}' (see its output above)."
    return f"Needs you: {name}, '{stop.title}'."


def run_automatic(root: Path, tool_ids: list[str]) -> int:
    """Run the automatic steps of the picked tools (all picks when `tool_ids` is empty).

    Returns:
        0 when every tool's required steps are done (or nothing is picked), 1 when a step
        failed, 2 when none of the named tools can run, 3 when a step needs the owner
        (failed wins over needs-you).

    Raises:
        KeyError: An unknown tool id.
    """
    ran: list[dict[str, str]] = []
    stops = []
    tools = _picked_tools(root, tool_ids)
    for tool in tools:
        stop = _run_tool(root, tool, ran)
        if stop:
            stops.append(stop)
    idle = NONE_USABLE if tool_ids else NOTHING_PICKED
    messages = [_stop_words(stop) for stop in stops] or [ALL_DONE if tools else idle]
    result = {"ran": ran, "stopped": [asdict(stop) for stop in stops], "messages": messages}
    print(json.dumps(result, indent=2))
    if tool_ids and not tools:
        return EXIT_NONE_USABLE
    reasons = {stop.reason for stop in stops}
    if progress.FAILED in reasons:
        return EXIT_FAILED
    return EXIT_NEEDS_YOU if reasons else 0
