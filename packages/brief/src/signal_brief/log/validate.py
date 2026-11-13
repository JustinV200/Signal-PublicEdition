"""validate_new_entry: the checks a NewEntry passes before it's logged.

Lengths (title 140, detail 600, undo 400 as JSON), the key pattern, no control or
invisible characters (signal_brief.text), a known kind, priority and source, and
the undo rules: a decision needs one, and untrusted entries never carry one, so
outside text can never be paired with an action a session might run.
"""

import json
import re

from signal_brief.log.entry import KIND_LETTERS, PRIORITIES, NewEntry, UndoAction
from signal_brief.text import check_key, check_text

MAX_TITLE_CHARS = 140
MAX_DETAIL_CHARS = 600
MAX_UNDO_CHARS = 400
SOURCE_PATTERN = re.compile(r"^[a-z0-9_-]{1,32}$")
# Claude Code tool names: Bash, Edit, mcp__server__tool.
TOOL_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def validate_new_entry(new: NewEntry) -> None:
    """Raise ValueError if `new` breaks a rule; return None if it's fine to log."""
    if new.kind not in KIND_LETTERS:
        raise ValueError(f"kind must be one of {', '.join(KIND_LETTERS)}")
    if new.priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {', '.join(PRIORITIES)}")
    if not isinstance(new.source, str) or not SOURCE_PATTERN.fullmatch(new.source):
        raise ValueError("bad source")
    if not isinstance(new.untrusted, bool):
        raise ValueError("untrusted must be true or false")
    if not check_text("title", new.title, MAX_TITLE_CHARS).strip():
        raise ValueError("title is empty")
    check_text("detail", new.detail, MAX_DETAIL_CHARS, allow_newlines=True)
    if new.key:
        check_key(new.key)
    _check_undo(new)


def _check_undo(new: NewEntry) -> None:
    """The undo rules: shape, length, and which entries may carry one."""
    if new.undo is None:
        if new.kind == "decision":
            raise ValueError("a decision needs an undo action")
        return
    if new.untrusted:
        raise ValueError("an untrusted entry can't carry an undo action")
    _check_undo_shape(new.undo)
    if len(json.dumps(new.undo)) > MAX_UNDO_CHARS:
        raise ValueError(f"undo is over {MAX_UNDO_CHARS} characters as JSON")


def _check_undo_shape(undo: UndoAction) -> None:
    if not isinstance(undo, dict) or set(undo) != {"tool", "args"}:
        raise ValueError('undo must be {"tool": <name>, "args": {...}}')
    if not isinstance(undo["tool"], str) or not TOOL_PATTERN.fullmatch(undo["tool"]):
        raise ValueError("undo tool must be a tool name like Bash or mcp__server__tool")
    if not isinstance(undo["args"], dict):
        raise ValueError("undo args must be an object")
