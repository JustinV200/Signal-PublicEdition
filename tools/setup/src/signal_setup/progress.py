"""Setup progress in .setup/progress.json, so a stopped setup resumes where it left off.

Shape: {"chosen": [tool ids], "answers": {"email": ...},
        "tools": {id: {"skipped": bool, "steps": {step id: "done"|"skipped"|"failed"}}}}
A tool is done when every required step that applies here is done; nothing else is stored.
"""

import json
from pathlib import Path
from typing import Any

from signal_setup.registry import Step, Tool

PROGRESS_FILE = Path(".setup") / "progress.json"
DONE, SKIPPED, FAILED, STARTED = "done", "skipped", "failed", "started"


def load(root: Path) -> dict[str, Any]:
    """The saved progress, or an empty one when setup never ran."""
    path = root / PROGRESS_FILE
    if not path.exists():
        return {"chosen": [], "answers": {}, "tools": {}}
    data = json.loads(path.read_text("utf-8"))
    for key, empty in (("chosen", []), ("answers", {}), ("tools", {})):
        data.setdefault(key, empty)
    return data


def save(root: Path, data: dict[str, Any]) -> None:
    """Write the progress (atomically, so a Ctrl+C mid-write can't corrupt it)."""
    path = root / PROGRESS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    tmp.replace(path)


def _entry(data: dict[str, Any], tool_id: str) -> dict[str, Any]:
    """The tool's record, created on first use."""
    return data["tools"].setdefault(tool_id, {"skipped": False, "steps": {}})


def step_status(data: dict[str, Any], tool_id: str, step_id: str) -> str:
    """'done', 'skipped', 'failed', or '' if the step never ran."""
    return data["tools"].get(tool_id, {}).get("steps", {}).get(step_id, "")


def set_step(data: dict[str, Any], tool_id: str, step_id: str, status: str) -> None:
    """Record a step's result. Running any step un-skips its tool."""
    entry = _entry(data, tool_id)
    entry["steps"][step_id] = status
    entry["skipped"] = False


def set_skipped(data: dict[str, Any], tool_id: str, skipped: bool = True) -> None:
    """Mark the whole tool skipped (it gets no config, MCP server, permissions or hooks)."""
    _entry(data, tool_id)["skipped"] = skipped
    if skipped and tool_id in data["chosen"]:
        data["chosen"].remove(tool_id)


def applicable_steps(tool: Tool, platform: str) -> tuple[Step, ...]:
    """The steps that apply on `platform`: scheduled-task steps (powershell) are Windows-only."""
    if platform == "windows":
        return tool.steps
    return tuple(s for s in tool.steps if not (s.argv and s.argv[0] == "powershell"))


def tool_status(data: dict[str, Any], tool: Tool, platform: str) -> str:
    """'done', 'skipped', 'failed', 'started' or '' (not started) for the whole tool."""
    entry = data["tools"].get(tool.id)
    if entry is None:
        return ""
    if entry.get("skipped"):
        return SKIPPED
    statuses = [step_status(data, tool.id, s.id) for s in applicable_steps(tool, platform)]
    # An optional settings step the user took counts too: placeholders left mean not done.
    required = [
        st
        for s, st in zip(applicable_steps(tool, platform), statuses, strict=True)
        if not s.optional or (s.kind == "settings" and st not in ("", SKIPPED))
    ]
    if all(st == DONE for st in required):
        return DONE
    return FAILED if FAILED in required else STARTED
