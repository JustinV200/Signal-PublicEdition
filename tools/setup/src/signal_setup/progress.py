"""Setup progress in .setup/progress.json, so a stopped setup resumes where it left off.

Shape: {"chosen": [tool ids], "answers": {"email": ..., "port": ...},
        "tools": {id: {"skipped": bool, "steps": {step id: "done"|"skipped"|"failed"}}}}
A tool is done when every required step that applies here is done (one with only optional
steps, when one of them is done or skipped); nothing else is stored. A tool setup never
touched has no entry at all; the lists then look at the machine instead (detect.py).

Setup has a record of a tool once it is skipped or one of its steps has a result
(has_record). The record says what the lists show and what `setup wire` adds. What wire
may take out again is decided by its own ledger (wiring/ledger.py), never by a record.
"""

import copy
import json
from collections.abc import Callable, Collection, Iterable
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


def write_state(path: Path, data: Any) -> None:
    """Write one of setup's own .setup/ files as JSON (atomically: a Ctrl+C can't corrupt it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    tmp.replace(path)


def save(root: Path, data: dict[str, Any]) -> None:
    """Write the progress (atomically, see write_state)."""
    write_state(root / PROGRESS_FILE, data)


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
    """Mark the whole tool skipped: setup adds no MCP server, permissions or hooks for it."""
    _entry(data, tool_id)["skipped"] = skipped
    if skipped and tool_id in data["chosen"]:
        data["chosen"].remove(tool_id)


def unpick(data: dict[str, Any], tool_id: str) -> None:
    """Take the tool out of the picks: skipped when setup has a record of it, else forgotten.

    A tool that was only picked (no step run) goes back to having no record, so one set up
    by hand still reads as found (detect.py), not as skipped.
    """
    if has_record(data, tool_id):
        set_skipped(data, tool_id)
        return
    data["tools"].pop(tool_id, None)
    if tool_id in data["chosen"]:
        data["chosen"].remove(tool_id)


def skip_unpicked(data: dict[str, Any], tool_ids: Iterable[str], chosen: Collection[str]) -> None:
    """Un-pick (unpick) every tool outside `chosen`: skipped only if setup has a record of it.

    A tool setup never touched, or only picked, stays without a record: picking one tool
    says nothing about the rest, which may have been set up by hand (detect.py), and a tool
    with no record is no part of the plan either way.
    """
    for tool_id in tool_ids:
        if tool_id not in chosen:
            unpick(data, tool_id)


def has_record(data: dict[str, Any], tool_id: str) -> bool:
    """True once setup has something to say about the tool: it's skipped, or a step ran.

    A tool that was only picked (a record with no step in it) has nothing recorded yet.
    """
    entry = data["tools"].get(tool_id, {})
    return bool(entry.get("skipped") or entry.get("steps"))


def adopt(data: dict[str, Any], tool_id: str, record: dict[str, Any] | None) -> None:
    """Start the tool's record from `record`, unless setup already has one for it.

    Called just before a step's result is written. `record` is what a finished setup would
    have left for a tool found already set up (detect.record_to_adopt; None when it isn't
    found), so the step's result lands on a tool that stays done.
    """
    if record and not has_record(data, tool_id):
        data["tools"][tool_id] = copy.deepcopy(record)


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
