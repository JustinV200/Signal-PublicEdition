"""Non-interactive commands the setup skill calls, one deterministic action each.

Every command prints JSON (or plain lines for `plan`) and never prompts, so Claude can
run them and only reason about a failure. Steps that need the user's own terminal
(passwords, Windows Hello, typed client IDs) are refused with the command to run instead.
"""

import json
import sys
from pathlib import Path
from typing import Any

from signal_setup import (
    platforms,
    prereqs,
    progress,
    registry,
    samples,
    settings,
    verify,
    wiring,
)
from signal_setup.steps import NEEDS_INPUT, run_step

NEEDS_TERMINAL = "needs_terminal"


class AgentAsker:
    """Answers from command-line flags; anything not given comes back as None (needs input)."""

    interactive = False

    def __init__(self, answer: str | None, value: str | None) -> None:
        self.answer, self.value, self.messages = answer, value, []

    def say(self, text: str) -> None:
        """Collect a message for the JSON result."""
        self.messages.append(text)

    def confirm(self, question: str, default: bool) -> bool | None:
        """The --answer flag (yes/no), or None."""
        return None if self.answer is None else self.answer == "yes"

    def text(self, question: str) -> str | None:
        """The --value flag, or None."""
        return self.value


def _print(data: Any) -> None:
    """Print `data` as indented JSON."""
    print(json.dumps(data, indent=2))


def list_tools(root: Path) -> int:
    """Every tool with its group, cost, platform label, support here, status, steps, and two flags.

    `picked`: the tool is among the user's picks (progress `chosen`), so a tool whose steps
    ran without a pick (the console the setup window builds first) isn't one. `wired`: a
    finished tool's servers and hooks are in Claude Code's config (read only).
    """
    data, platform = progress.load(root), platforms.current()
    tools = registry.load()
    wired = wiring.wired_tools(root, tools, data, platform)
    _print(
        [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "group": t.group,
                "cost": t.cost,
                "platform": platforms.label(t),
                "supported_here": platforms.is_supported(t, platform),
                "status": progress.tool_status(data, t, platform) or "not set up",
                "picked": t.id in data["chosen"],
                "wired": t.id in wired,
                "needs": list(t.needs),
                "prereqs": list(t.prereqs),
                "steps": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "kind": s.kind,
                        "optional": s.optional,
                        "default": s.default,
                        "terminal": s.terminal,
                        "automatic": s.is_automatic(),
                        "text": s.text,
                        "doc": s.doc,
                        "group": s.group,
                        "command": " ".join(s.argv),
                        "status": progress.step_status(data, t.id, s.id),
                    }
                    for s in progress.applicable_steps(t, platform)
                ],
            }
            for t in tools
        ]
    )
    return 0


def check_prereqs(tool_ids: list[str]) -> int:
    """Which prerequisites of the given tools (default all) are missing."""
    tools = [registry.by_id(i) for i in tool_ids] or list(registry.load())
    names = [n for t in tools for n in t.all_prereqs()]
    _print([{"name": p.name, "get_it": p.hint} for p in prereqs.missing(names)])
    return 0


def choose(root: Path, tool_ids: list[str]) -> int:
    """Record the user's picks; every other tool is marked skipped (gets no wiring)."""
    data = progress.load(root)
    chosen = [registry.by_id(i).id for i in tool_ids]
    for tool in registry.load():
        progress.set_skipped(data, tool.id, tool.id not in chosen)
    data["chosen"] = chosen
    progress.save(root, data)
    _print({"chosen": chosen})
    return 0


def apply(root: Path, tool_id: str, step_id: str, answer: str | None, value: str | None) -> int:
    """Run one step. Exit 0 when done or skipped, 1 when failed, 3 when it needs the user."""
    tool = registry.by_id(tool_id)
    step = tool.step(step_id)
    if step.terminal or step.kind == "samples":
        how = "setup samples ..." if step.kind == "samples" else f"setup step {tool.id} {step.id}"
        _print({"status": NEEDS_TERMINAL, "run_in_user_terminal": how})
        return 3
    data = progress.load(root)
    asker = AgentAsker(answer, value)
    status = run_step(root, tool, step, data, asker)
    progress.save(root, data)
    _print({"tool": tool.id, "step": step.id, "status": status, "messages": asker.messages})
    return {progress.FAILED: 1, NEEDS_INPUT: 3}.get(status, 0)


def mark(root: Path, tool_id: str, step_id: str, status: str) -> int:
    """Record a step the user did themselves (done) or chose to skip.

    Exit 3, with the ids left, when `done` is asked for a settings step whose config
    still holds placeholders or is missing a file: the step isn't done until every
    value is set.
    """
    step = registry.by_id(tool_id).step(step_id)  # validates both ids
    left = _placeholders_left(root, tool_id, step) if status == progress.DONE else []
    if left:
        _print({"tool": tool_id, "step": step_id, "status": NEEDS_INPUT, "placeholders_left": left})
        return 3
    data = progress.load(root)
    progress.set_step(data, tool_id, step_id, status)
    progress.save(root, data)
    _print({"tool": tool_id, "step": step_id, "status": status})
    return 0


def _placeholders_left(root: Path, tool_id: str, step: registry.Step) -> list[str]:
    """Ids of placeholders and missing files in a settings step's config group ([] otherwise)."""
    schema = settings.load(tool_id) if step.kind == "settings" else None
    if schema is None:
        return []
    return [s.id for s in settings.leftovers(root, schema, step.group)]


def plan(root: Path) -> int:
    """Print the permissions summary the user confirms before `wire --yes`."""
    built = wiring.build_plan(registry.load(), progress.load(root), platforms.current())
    print("\n".join(wiring.summary_lines(built)))
    return 0


def wire(root: Path, confirmed: bool) -> int:
    """Write the plan; refuses without --yes (the user's one confirmation)."""
    if not confirmed:
        print("Show the user `setup plan`, get their OK, then run `setup wire --yes`.")
        return 3
    tools, platform = registry.load(), platforms.current()
    notes = wiring.apply_plan(
        root, tools, wiring.build_plan(tools, progress.load(root), platform), platform
    )
    _print({"written": [".mcp.json", ".claude/settings.local.json"], "notes": notes})
    return 0


def verify_tools(root: Path, tool_ids: list[str]) -> int:
    """Verify the given tools (default: every finished one). Exit 1 if any check fails.

    A failed check without a summary line also gets `output`, its last output line, so
    the setup skill can reason about the error.
    """
    data, platform = progress.load(root), platforms.current()
    tools = [registry.by_id(i) for i in tool_ids] or [
        t for t in registry.load() if progress.tool_status(data, t, platform) == progress.DONE
    ]
    results = {t.id: verify.check(root, t, data) for t in tools}
    _print({tool_id: _verify_row(r) for tool_id, r in results.items()})
    return 0 if all(r.passed for r in results.values()) else 1


def _verify_row(result: verify.CheckResult) -> dict[str, Any]:
    """One tool's `setup verify` entry: ok, words, fix, command, and output when there is one."""
    row = {"ok": result.passed, "words": result.words, "fix": result.fix, "command": result.command}
    if result.output:
        row["output"] = result.output
    return row


def samples_command(root: Path, action: str, args: list[str], kind: str) -> int:
    """`setup samples files|paste|mail|keep|count`: the deterministic parts of the samples step."""
    if action == "files":
        _print(samples.import_paths(root, [Path(a) for a in args], kind))
    elif action == "paste":
        _print([samples.save_sample(root, kind, "pasted", sys.stdin.read()).name])
    elif action == "mail":
        _print(
            [
                {"number": n, "subject": c["subject"], "text": c["text"]}
                for n, c in enumerate(samples.fetch_sent(root, *args[:1]), 1)
            ]
        )
    elif action == "keep":
        _print(samples.save_candidates(root, [int(a) for a in args]))
    low, high = samples.TARGET_RANGE
    _print({"samples": samples.sample_count(root), "target": f"{low}-{high}"})
    return 0
