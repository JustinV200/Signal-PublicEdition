"""The interactive setup: intro, checklist, each tool's steps, one confirmation, wiring, checks.

Progress is saved after every step, so Ctrl+C and running `setup` again resumes. Finished
steps aren't repeated unless the user re-runs one tool with `setup <tool>`.
"""

from pathlib import Path
from typing import Any

from signal_setup import platforms, progress, registry, verify, wiring
from signal_setup.intro import intro_text
from signal_setup.prereqs import missing
from signal_setup.registry import Tool
from signal_setup.steps import run_step
from signal_setup.terminal import BOLD, TerminalAsker, style
from signal_setup.ui import tour
from signal_setup.ui.checklist import choose


def _warn_needs(tool: Tool, chosen: list[str], asker: TerminalAsker) -> None:
    """Point out a tool this one builds on that isn't picked."""
    for need in tool.needs:
        if need not in chosen:
            needed = registry.by_id(need).name
            asker.say(f"Note: {tool.name} builds on {needed}, which isn't picked.")


def _run_tool(root: Path, tool: Tool, data: dict[str, Any], rerun: bool) -> None:
    """Run the tool's steps in order. Skipping a required step skips the whole tool."""
    asker = TerminalAsker()
    print(style(f"\n== {tool.name} ==", BOLD))
    for prereq in missing(tool.prereqs):
        asker.say(f"Needs {prereq.name}: {prereq.hint}")
    for step in progress.applicable_steps(tool, platforms.current()):
        if not rerun and progress.step_status(data, tool.id, step.id) == progress.DONE:
            continue
        question = f"{tool.name}: {step.title}?"
        wanted = step.kind == "confirm" or asker.confirm(question, step.default)
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


def _wire(root: Path, data: dict[str, Any]) -> None:
    """Show the permissions summary, ask once, then write the config."""
    tools, platform = registry.load(), platforms.current()
    plan = wiring.build_plan(tools, data, platform)
    print(style("\nWhat setup will add to Claude Code:", BOLD))
    print("\n".join(wiring.summary_lines(plan)))
    if not TerminalAsker().confirm("Write this?", True):
        print("Nothing written. Run `setup` again when you're ready.")
        return
    for note in wiring.apply_plan(root, tools, plan, platform):
        print(note)
    print("Written. Restart Claude Code (or run /mcp) to load the tools.")


def run_setup(root: Path, only_tool: str | None = None) -> None:
    """The whole interactive setup, or just one tool's steps when `only_tool` is given."""
    data = progress.load(root)
    tools = registry.load()
    if only_tool:
        chosen = [registry.by_id(only_tool).id]
        data["chosen"] = list(dict.fromkeys([*data["chosen"], only_tool]))
    else:
        print(intro_text())
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
