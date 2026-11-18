"""Setup progress in .setup/progress.json, so a stopped setup resumes where it left off.

Shape: {"chosen": [tool ids], "answers": {"email": ..., "port": ...},
        "tools": {id: {"skipped": bool, "steps": {step id: "done"|"skipped"|"failed"}}}}
A tool is done when every required step that applies here is done (one with only optional
steps, when one of them is done or skipped); nothing else is stored.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from signal_setup.registry import Step, Tool

PROGRESS_FILE = Path(".setup") / "progress.json"
DONE, SKIPPED, FAILED, STARTED = "done", "skipped", "failed", "started"

# The console's port: `setup` and `setup ui` store their --port as this answer, and the
# console's logon step fills {port} with it. Until one is stored, the default stands.
PORT_ANSWER = "port"
DEFAULT_PORT = 8790
# The ports `--port` accepts: unprivileged and valid, the same range as the console's
# register.ps1 and unregister.ps1 (ValidateRange), so a stored port always registers.
MIN_PORT, MAX_PORT = 1024, 65535
DEFAULT_ANSWERS = {PORT_ANSWER: str(DEFAULT_PORT)}


def parse_port(value: object) -> int:
    """`value` (a --port argument or the stored answer) as a port.

    Raises:
        ValueError: It isn't a whole number from MIN_PORT to MAX_PORT.
    """
    try:
        port = int(str(value))
    except ValueError:
        port = -1
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError(f"{str(value)!r} isn't a port from {MIN_PORT} to {MAX_PORT}")
    return port


def stored_port(answers: dict[str, Any], say: Callable[[str], None]) -> int:
    """The stored `port` answer, or the default (after a one-line note via `say`) when it's bad.

    A hand-edited progress.json may hold anything; setup itself stores only valid ports.
    The setup window and the logon step's {port} both use this, so they agree.
    """
    try:
        return parse_port(answers.get(PORT_ANSWER, DEFAULT_PORT))
    except ValueError as error:
        say(f"The stored console port {error}; using {DEFAULT_PORT}.")
        return DEFAULT_PORT


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
    steps = applicable_steps(tool, platform)
    statuses = [step_status(data, tool.id, s.id) for s in steps]
    # An optional settings step the user took counts too: placeholders left mean not done.
    required = [
        st
        for s, st in zip(steps, statuses, strict=True)
        if not s.optional or (s.kind == "settings" and st not in ("", SKIPPED))
    ]
    # A tool whose steps are all optional (agents, copytone) isn't done the moment it's
    # picked: one of them must be done or skipped first.
    if steps and all(s.optional for s in steps) and not {DONE, SKIPPED} & set(statuses):
        return FAILED if FAILED in statuses else STARTED
    if all(st == DONE for st in required):
        return DONE
    return FAILED if FAILED in required else STARTED
