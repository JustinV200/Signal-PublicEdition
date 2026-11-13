"""Check a console button's action and arguments and turn it into a fixed plan to run.

Each plan names one step the console server runs itself (the voice hub's
start/stop, or one whiteboard CLI command with fixed arguments) plus the
words the console shows. Nothing from the page reaches a command except a
save name, and only one that is in the whiteboard's current save list.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Actions that touch the same thing share a lock, so a double click (or a load
# during a calibrate) is refused while the first one runs.
VOICE_LOCK = "voice"
BOARD_LOCK = "board"

BOARD_LOAD = "board.load"
BOARD_UPDATE = "board.update"
# The actions that name a save, and so need the saves read fresh from the whiteboard.
SAVE_ACTIONS = frozenset({BOARD_LOAD, BOARD_UPDATE})
TODO_REFRESHER = "todo"
TASKS_REFRESHER = "tasks"


class ActionError(ValueError):
    """The action can't run: unknown, or a bad or stale argument."""


@dataclass(frozen=True)
class HubStep:
    """Start (True) or stop (False) the voice hub, as `console hub start|stop` does."""

    start: bool


@dataclass(frozen=True)
class WhiteboardStep:
    """One `whiteboard ...` CLI command.

    Attributes:
        args: The arguments after `whiteboard` (fixed, apart from a checked save name).
        done_text: What the console says when it worked.
        shows_output: Add the command's first output line (calibrate and realign
            say what they found).
    """

    args: tuple[str, ...]
    done_text: str
    shows_output: bool = False


Step = HubStep | WhiteboardStep


@dataclass(frozen=True)
class ActionPlan:
    """A checked button click: what to show, which lock it holds, and what to run."""

    display_text: str
    lock: str
    step: Step


_TODO_SHOW = WhiteboardStep(("todo", "show"), "The to-do list is on the board.")
_IDLE_SHOW = WhiteboardStep(("idle", "show"), "The idle board is on the board.")
_TASKS_SHOW = WhiteboardStep(("tasks", "show"), "Redrew the task grid.", shows_output=True)
_FIXED_PLANS = {
    "voice.start": ActionPlan("Start the voice hub", VOICE_LOCK, HubStep(start=True)),
    "voice.stop": ActionPlan("Stop the voice hub", VOICE_LOCK, HubStep(start=False)),
    "board.todo": ActionPlan("Show the to-do list on the board", BOARD_LOCK, _TODO_SHOW),
    "board.idle": ActionPlan("Show the idle board on the board", BOARD_LOCK, _IDLE_SHOW),
    "board.realign": ActionPlan(
        "Realign the board",
        BOARD_LOCK,
        WhiteboardStep(("realign",), "Realign finished.", shows_output=True),
    ),
    "board.calibrate": ActionPlan(
        "Fully calibrate the board",
        BOARD_LOCK,
        WhiteboardStep(("calibrate",), "Calibration finished.", shows_output=True),
    ),
}
# refresher (a save's meta.json, from a fixed enum) -> what Update shows and runs.
# Update redraws from live data; it never loads the old save.
_REFRESH_PLANS = {
    TASKS_REFRESHER: ("Update the task grid on the board", _TASKS_SHOW),
    TODO_REFRESHER: ("Update the to-do list on the board", _TODO_SHOW),
}


def plan_action(
    action: Any, args: Mapping[str, Any], saves: Mapping[str, str | None]
) -> ActionPlan:
    """Check a button click and return what to run.

    Args:
        action: One of voice.start, voice.stop, board.load, board.todo, board.idle, board.realign,
            board.calibrate, board.update.
        args: The action's arguments; board.load and board.update need `name`
            (board.update takes `{view: "todo"}` for the to-do list instead).
        saves: The whiteboard saves that exist now, each mapped to its refresher.

    Raises:
        ActionError: Unknown action, a name that isn't a current save, or
            board.update for a save with no refresher.
    """
    if action == BOARD_LOAD:
        name = _current_save(args, saves, BOARD_LOAD)
        # "--" ends the options, so a save named like "-x" is still read as the name.
        quoted = _quoted(name)
        step = WhiteboardStep(("load", "--no-ink", "--", name), f"Loaded the board {quoted}.")
        return ActionPlan(f"Load the board {quoted}", BOARD_LOCK, step)
    if action == BOARD_UPDATE:
        return _update(args, saves)
    if isinstance(action, str) and action in _FIXED_PLANS:
        return _FIXED_PLANS[action]
    raise ActionError(f"unknown action {action!r}")


def _update(args: Mapping[str, Any], saves: Mapping[str, str | None]) -> ActionPlan:
    if args.get("view") == TODO_REFRESHER:
        shown, step = _REFRESH_PLANS[TODO_REFRESHER]
        return ActionPlan(shown, BOARD_LOCK, step)
    name = _current_save(args, saves, BOARD_UPDATE)
    refresher = saves.get(name)
    if refresher not in _REFRESH_PLANS:
        raise ActionError(f"the board {_quoted(name)} has no refresher, so it can't be updated")
    shown, step = _REFRESH_PLANS[refresher]
    return ActionPlan(f"{shown} ({_quoted(name)})", BOARD_LOCK, step)


def _current_save(args: Mapping[str, Any], saves: Mapping[str, str | None], action: str) -> str:
    """args' `name`, which must be one of the current saves."""
    name = args.get("name")
    if not isinstance(name, str) or name not in saves:
        raise ActionError(f"{action} needs the name of a current whiteboard save")
    return name


def _quoted(name: str) -> str:
    # ASCII-only JSON quoting escapes quotes, newlines and bidi overrides, so a save
    # name can't disguise itself as part of the words around it.
    return json.dumps(name, ensure_ascii=True)
