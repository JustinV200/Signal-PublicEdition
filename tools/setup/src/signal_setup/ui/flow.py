"""The interactive setup: intro, missing programs, checklist, each tool's steps, one
confirmation, wiring, checks. Also `setup step`: one step on its own, with no wiring.

Progress is saved after every step, so Ctrl+C and running `setup` again resumes. Finished
steps aren't repeated unless the user re-runs one tool with `setup <tool>`.
"""

import copy
from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, registry, verify, wiring
from signal_setup.intro import intro_text
from signal_setup.prereqs import missing
from signal_setup.registry import Tool
from signal_setup.steps import NEEDS_INPUT, run_step
from signal_setup.terminal import BOLD, TerminalAsker, style
from signal_setup.ui import tour
from signal_setup.ui.checklist import choose

# `setup step`'s exit codes, as `setup apply` gives them: 1 failed, 3 still needs the user.
STEP_EXIT_CODES = {progress.FAILED: 1, NEEDS_INPUT: 3}
# How `setup step` ends: the step's result in words.
STEP_RESULT_WORDS = {
    progress.DONE: "done",
    progress.SKIPPED: "skipped",
    progress.FAILED: "failed (see above)",
    NEEDS_INPUT: "not done yet",
}


def _warn_needs(tool: Tool, chosen: list[str], asker: TerminalAsker) -> None:
    """Point out a tool this one builds on that isn't picked."""
    for need in tool.needs:
        if need not in chosen:
            needed = registry.by_id(need).name
            asker.say(f"Note: {tool.name} builds on {needed}, which isn't picked.")


def _announce(tool: Tool, asker: TerminalAsker) -> None:
    """The tool's heading, then any program it needs that isn't installed."""
    print(style(f"\n== {tool.name} ==", BOLD))
    for prereq in missing(tool.prereqs):
        asker.say(f"Needs {prereq.name}: {prereq.how_to_get()}")


def _run_tool(root: Path, tool: Tool, data: dict[str, Any], rerun: bool) -> None:
    """Run the tool's steps in order. Skipping a required step skips the whole tool.

    A required run or copy step just runs (the tool was picked, so there's nothing to
    ask); other steps ask first, so an optional one can be skipped.
    """
    asker = TerminalAsker()
    _announce(tool, asker)
    for step in progress.applicable_steps(tool, platforms.current()):
        if not rerun and progress.step_status(data, tool.id, step.id) == progress.DONE:
            continue
        if step.kind == "confirm":
            wanted = True  # the step is its own question
        elif not step.optional and step.kind in registry.UNATTENDED_KINDS:
            asker.say(f"{tool.name}: {step.title}")
            wanted = True
        else:
            wanted = asker.confirm(f"{tool.name}: {step.title}?", step.default)
        if not wanted:
            if not step.optional:
                asker.say(f"That step is required, so {tool.name} is skipped for now.")
                progress.set_skipped(data, tool.id)
                return
            progress.set_step(data, tool.id, step.id, progress.SKIPPED)
            continue
        status = run_step(root, tool, step, data, asker)
        progress.save(root, data)
        if status != progress.DONE and not step.optional:
            asker.say(f"{tool.name} isn't finished. Fix the above, then run: setup {tool.id}")
            return


def _say_missing_programs(tools: tuple[Tool, ...]) -> None:
    """List the programs any tool needs that aren't installed, as the window's first page does."""
    lacking = missing([name for tool in tools for name in tool.all_prereqs()])
    if not lacking:
        print("\nEverything the tools need is installed.")
        return
    print("\nMissing programs (only the tools that use one need it):")
    for prereq in lacking:
        print(f"  ! missing: {prereq.name}, {prereq.how_to_get()}")


def _wire(root: Path, data: dict[str, Any]) -> None:
    """Show the permissions summary, ask once, then write the config."""
    tools, platform = registry.load(), platforms.current()
    plan = wiring.build_plan(tools, data, platform)
    print(style("\nWhat setup will add to Claude Code:", BOLD))
    print("\n".join(wiring.summary_lines(plan)))
    if not TerminalAsker().confirm("Add to Claude Code?", True):
        print("Nothing written. Run `setup` again when you're ready.")
        return
    for note in wiring.apply_plan(root, tools, plan, platform):
        print(note)
    print("Written. Restart Claude Code (or run /mcp) to load the tools.")


def _save_changes(root: Path, before: dict[str, Any], after: dict[str, Any]) -> None:
    """Save only what one run changed (step statuses, answers) onto the progress as it is now.

    `setup step` may wait at a prompt for minutes while the setup window records other
    steps, picks and skips; saving its whole early snapshot would undo those. A settings
    step can re-run other steps, so every status that changed counts, not just one.
    Nothing changed (say the step still needs input): nothing is written.
    """
    fresh = progress.load(root)
    changed = False
    for tool_id, entry in after["tools"].items():
        for step_id, status in entry.get("steps", {}).items():
            if status != progress.step_status(before, tool_id, step_id):
                progress.set_step(fresh, tool_id, step_id, status)
                changed = True
    for key, value in after["answers"].items():
        if before["answers"].get(key) != value:
            fresh["answers"][key] = value
            changed = True
    if changed:
        progress.save(root, fresh)


def run_one_step(root: Path, tool_id: str, step_id: str) -> int:
    """`setup step <tool> <step>`: run that one step at the terminal, then stop.

    No "Install?" question first and no wiring after (nothing is written to Claude
    Code's config): the setup window's "Open a terminal" uses this for a step that takes
    a secret, and the window adds the tool to Claude Code itself.

    Returns:
        0 done or skipped, 1 failed, 3 still needs input.

    Raises:
        KeyError: An unknown tool or step id (main turns it into exit 2).
    """
    tool = registry.by_id(tool_id)
    step = tool.step(step_id)
    asker = TerminalAsker()
    _announce(tool, asker)
    data = progress.load(root)
    before = copy.deepcopy(data)
    status = run_step(root, tool, step, data, asker)
    _save_changes(root, before, data)
    print(f"\n{step.title}: {STEP_RESULT_WORDS[status]}.")
    print("If the setup window is open, press Check again there. You can close this window.")
    return STEP_EXIT_CODES.get(status, 0)


def run_setup(root: Path, only_tool: str | None = None) -> None:
    """The whole interactive setup, or just one tool's steps when `only_tool` is given."""
    data = progress.load(root)
    tools = registry.load()
    if only_tool:
        chosen = [registry.by_id(only_tool).id]
        data["chosen"] = list(dict.fromkeys([*data["chosen"], only_tool]))
    else:
        print(intro_text())
        _say_missing_programs(tools)
        chosen = choose(tools, data, platforms.current())
        for tool in tools:
            if tool.id not in chosen:
                progress.set_skipped(data, tool.id)
        data["chosen"] = chosen
    progress.save(root, data)
    for tool_id in chosen:
        tool = registry.by_id(tool_id)
        _warn_needs(tool, data["chosen"], TerminalAsker())
        _run_tool(root, tool, data, rerun=bool(only_tool))
    _wire(root, data)
    for tool_id in chosen:
        print(verify.report_line(root, registry.by_id(tool_id), data))
    if not only_tool and TerminalAsker().confirm("Take the short tour of how it all works?", False):
        tour.run(root)
