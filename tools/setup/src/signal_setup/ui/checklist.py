"""The tool checklist: every tool with its platform label and status; the user picks by number.

Tools that don't run on this OS are dimmed and labelled "not on <os>", and can't be picked.
"""

from typing import Any

from signal_setup import platforms, progress
from signal_setup.registry import Tool
from signal_setup.terminal import DIM, style

STATUS_WORDS = {
    "": "not set up",
    progress.STARTED: "half done",
    progress.DONE: "done",
    progress.SKIPPED: "skipped",
    progress.FAILED: "failed",
}


def _row(number: int, tool: Tool, data: dict[str, Any], picked: bool, platform: str) -> str:
    """One checklist line: tick, number, name, platform label, status, any OS limit."""
    status = STATUS_WORDS[progress.tool_status(data, tool, platform)]
    mark = "x" if picked else " "
    line = f"[{mark}] {number:2}. {tool.name}  ({platforms.label(tool)}; {status})"
    if not platforms.is_supported(tool, platform):
        return style(f"{line}  not on {platform}: Windows only", DIM)
    return f"{line}\n         {tool.description}"


def _toggle(answer: str, tools: tuple[Tool, ...], picked: set[str], platform: str) -> str:
    """Apply one checklist answer to `picked`. Returns a problem to show, or ''."""
    supported = {t.id for t in tools if platforms.is_supported(t, platform)}
    if answer in ("all", "none"):
        picked.clear()
        picked.update(supported if answer == "all" else ())
        return ""
    for token in answer.replace(",", " ").split():
        if not token.isdigit() or not 1 <= int(token) <= len(tools):
            return f"{token!r} isn't a number from the list."
        tool = tools[int(token) - 1]
        if tool.id not in supported:
            return f"{tool.name} doesn't run on {platform}."
        picked.symmetric_difference_update({tool.id})
    return ""


def choose(tools: tuple[Tool, ...], data: dict[str, Any], platform: str) -> list[str]:
    """Show the checklist until the user presses Enter. Returns the picked ids in setup order."""
    picked = {t for t in data["chosen"] if any(t == tool.id for tool in tools)}
    while True:
        print("\nPick the tools you want (type numbers to tick or untick, 'all', 'none'):")
        for number, tool in enumerate(tools, 1):
            print(_row(number, tool, data, tool.id in picked, platform))
        answer = input("\nNumbers, or Enter when done: ").strip().lower()
        if not answer:
            return [t.id for t in tools if t.id in picked]
        problem = _toggle(answer, tools, picked, platform)
        if problem:
            print(problem)
