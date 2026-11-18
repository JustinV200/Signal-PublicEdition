"""The hook rows: are the console's turn and session hooks in Claude Code's settings, once each?

A hook counts as installed when it is in either settings file (the checked-in
.claude/settings.json or .claude/settings.local.json, where setup's `wire`
writes them). One in both files fires twice per event, which is reported too.
The files are only read; a missing or unparsable file holds no hooks.
"""

from pathlib import Path
from typing import Any

from signal_console.health.inputs import HealthPaths
from signal_console.health.row import ATTENTION, FAIL, OK, SETUP_COMMAND, HealthRow
from signal_console.state_files import read_json

TURN_MODULE = "signal_console.hooks.turn"
SESSION_MODULE = "signal_console.hooks.session"
# The events each hook must be registered for (setup's registry entry for the console).
TURN_EVENTS = ("UserPromptSubmit", "Stop", "StopFailure", "Notification")
SESSION_EVENTS = ("SessionStart", "PostModelSwitch")
# Setup writes the hooks; Claude Code reads hooks only when a session starts.
HOOK_FIX = "Add the console's hooks with setup, then restart Claude Code."


def hook_rows(paths: HealthPaths) -> list[HealthRow]:
    """The turn hook row, the session hook row, then the "fires twice" row."""
    settings = [(path, _hooks_of(path)) for path in paths.settings_files]
    turn = _files_per_event(settings, TURN_MODULE, TURN_EVENTS)
    session = _files_per_event(settings, SESSION_MODULE, SESSION_EVENTS)
    return [
        _installed_row("turn-hook", "Turn hook", turn),
        _installed_row("session-hook", "Session hook", session),
        _twice_row(turn | session),
    ]


def _hooks_of(path: Path) -> dict[str, Any]:
    hooks = (read_json(path) or {}).get("hooks")
    return hooks if isinstance(hooks, dict) else {}


def _files_per_event(
    settings: list[tuple[Path, dict[str, Any]]], module: str, events: tuple[str, ...]
) -> dict[str, list[Path]]:
    # For each event, the settings files with an entry that runs `module`.
    return {
        event: [path for path, hooks in settings if _runs_module(hooks.get(event), module)]
        for event in events
    }


def _runs_module(groups: Any, module: str) -> bool:
    # groups: [{matcher?, hooks: [{type, command, args?}]}], as Claude Code's settings hold them.
    if not isinstance(groups, list):
        return False
    entries = [
        entry
        for group in groups
        if isinstance(group, dict) and isinstance(group.get("hooks"), list)
        for entry in group["hooks"]
        if isinstance(entry, dict)
    ]
    return any(_entry_runs(entry, module) for entry in entries)


def _entry_runs(entry: dict[str, Any], module: str) -> bool:
    # The module is an `args` item, or part of a one-string `command`.
    args = entry.get("args")
    return (isinstance(args, list) and module in args) or module in str(entry.get("command", ""))


def _installed_row(row_id: str, name: str, files: dict[str, list[Path]]) -> HealthRow:
    missing = [event for event, found in files.items() if not found]
    if not missing:
        words = f"Registered for all {len(files)} events ({', '.join(files)})."
        return HealthRow(row_id, name, OK, "installed", words)
    state = "missing" if len(missing) == len(files) else "partly missing"
    words = f"Not registered for {', '.join(missing)}, so the console misses those events."
    return HealthRow(row_id, name, FAIL, state, words, HOOK_FIX, SETUP_COMMAND)


def _twice_row(files: dict[str, list[Path]]) -> HealthRow:
    doubled = [event for event, found in files.items() if len(found) > 1]
    if not doubled:
        return HealthRow(
            "hooks-twice",
            "Hooks fire once",
            OK,
            "once",
            "No console hook is in both settings files.",
        )
    words = f"The console's {', '.join(doubled)} hook is in both settings files, so it fires twice."
    fix = (
        "Remove the console's hooks from .claude/settings.json; "
        "setup keeps them in .claude/settings.local.json."
    )
    return HealthRow("hooks-twice", "Hooks fire once", ATTENTION, "twice", words, fix)
