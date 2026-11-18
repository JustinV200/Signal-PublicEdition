"""Check a console button's action and arguments and turn it into a fixed plan to run.

Each plan names one step the console server runs itself (the voice hub's
start/stop, or one whiteboard CLI command with fixed arguments) plus the
words the console shows. Nothing from the page reaches a command except a
save name, and only one that is in the whiteboard's current save list.
"""

import json
import unicodedata
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
# Characters a save name could hide behind: controls, bidi and other invisible format
# characters, line and paragraph separators, and lone surrogates (by category), plus
# the default-ignorable letters and marks no category catches: Hangul fillers,
# variation selectors, the combining grapheme joiner and the like (an explicit list,
# the same as the page's, so a Unicode update on one side can't make them differ).
_HIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp", "Cs"})
_INVISIBLE_RANGES = (
    (0x034F, 0x034F),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x2065, 0x2065),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0xE0000, 0xE0FFF),
)


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


_TODO_SHOW = WhiteboardStep(("todo", "show"), "The to-do list is on the projector.")
_IDLE_SHOW = WhiteboardStep(("idle", "show"), "The idle board is on the projector.")
_TASKS_SHOW = WhiteboardStep(("tasks", "show"), "Redrew the task grid.", shows_output=True)
_FIXED_PLANS = {
    # The words match the page's buttons and Commands, so a chat row reads like the click.
    "voice.start": ActionPlan("Start voice", VOICE_LOCK, HubStep(start=True)),
    "voice.stop": ActionPlan("Stop voice", VOICE_LOCK, HubStep(start=False)),
    "board.todo": ActionPlan("Send to projector: to-do list", BOARD_LOCK, _TODO_SHOW),
    "board.idle": ActionPlan("Send to projector: idle board", BOARD_LOCK, _IDLE_SHOW),
    "board.realign": ActionPlan(
        "Realign whiteboard",
        BOARD_LOCK,
        WhiteboardStep(("realign",), "Realign finished.", shows_output=True),
    ),
    "board.calibrate": ActionPlan(
        "Full calibrate",
        BOARD_LOCK,
        WhiteboardStep(("calibrate",), "Calibration finished.", shows_output=True),
    ),
}
# refresher (a save's meta.json, from a fixed enum) -> what board.update (the page's
# "Show live version") runs. It redraws from live data; it never loads the old save.
_REFRESH_STEPS = {TASKS_REFRESHER: _TASKS_SHOW, TODO_REFRESHER: _TODO_SHOW}


def plan_action(
    action: Any, args: Mapping[str, Any], saves: Mapping[str, str | None]
) -> ActionPlan:
    """Check a button click and return what to run.

    Args:
        action: One of voice.start, voice.stop, board.load, board.todo, board.idle, board.realign,
            board.calibrate, board.update.
        args: The action's arguments; board.load and board.update need `name`
            (board.update still takes `{view: "todo"}` for the to-do list; the page
            no longer sends it, but a tab loaded before the update could still send it).
        saves: The whiteboard saves that exist now, each mapped to its refresher.

    Raises:
        ActionError: Unknown action, a name that isn't a current save, or
            board.update for a save with no refresher.
    """
    if action == BOARD_LOAD:
        name = _current_save(args, saves, BOARD_LOAD)
        # "--" ends the options, so a save named like "-x" is still read as the name.
        quoted = _quoted(name)
        step = WhiteboardStep(("load", "--no-ink", "--", name), f"Sent {quoted} to the projector.")
        return ActionPlan(f"Send to projector: {quoted}", BOARD_LOCK, step)
    if action == BOARD_UPDATE:
        return _update(args, saves)
    if isinstance(action, str) and action in _FIXED_PLANS:
        return _FIXED_PLANS[action]
    raise ActionError(f"unknown action {action!r}")


def _update(args: Mapping[str, Any], saves: Mapping[str, str | None]) -> ActionPlan:
    if args.get("view") == TODO_REFRESHER:
        return ActionPlan("Update the to-do list", BOARD_LOCK, _REFRESH_STEPS[TODO_REFRESHER])
    name = _current_save(args, saves, BOARD_UPDATE)
    refresher = saves.get(name)
    quoted = _quoted(name)
    if refresher not in _REFRESH_STEPS:
        raise ActionError(f"the saved board {quoted} has no live data to redraw it from")
    return ActionPlan(f"Show live version: {quoted}", BOARD_LOCK, _REFRESH_STEPS[refresher])


def _current_save(args: Mapping[str, Any], saves: Mapping[str, str | None], action: str) -> str:
    """args' `name`, which must be one of the current saves."""
    name = args.get("name")
    if not isinstance(name, str) or name not in saves:
        raise ActionError(f"{action} needs the name of a current saved board")
    return name


def _quoted(name: str) -> str:
    # JSON quoting escapes quotes and newlines, and the hidden characters are escaped
    # too, so a save name can't disguise itself as part of the words around it; every
    # other letter shows as typed. The page's quoteName (web state/actions/actionLabels.ts)
    # gives the same text, so a row doesn't change as the server's echo lands.
    return "".join(_escape_hidden(char) for char in json.dumps(name, ensure_ascii=False))


def _escape_hidden(char: str) -> str:
    """`char`, or its `\\uXXXX` escape when it is hidden (see _INVISIBLE_RANGES)."""
    code = ord(char)
    is_invisible = any(low <= code <= high for low, high in _INVISIBLE_RANGES)
    if not is_invisible and unicodedata.category(char) not in _HIDDEN_CATEGORIES:
        return char
    if code > 0xFFFF:  # As a UTF-16 pair, like JSON's own escapes and the page's.
        code -= 0x10000
        return f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}"
    return f"\\u{code:04x}"
