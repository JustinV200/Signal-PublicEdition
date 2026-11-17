"""The text a file will hold after an Edit, MultiEdit or NotebookEdit, for the content hooks.

Scanning only an edit's new_string misses code split across edits (a URL added in one
edit, the fetch call in the next), so the hooks scan the whole file as it will be:
the current contents with the replacement applied.
"""

import json
from pathlib import Path
from typing import Any

NOTEBOOK_EDIT = "NotebookEdit"
MULTI_EDIT = "MultiEdit"
_REMOVING_MODES = frozenset({"replace", "delete"})


def _read_current(path: Path) -> str:
    """The file's text, or "" when it doesn't exist yet. Other read errors propagate."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _apply_edit(text: str, edit: dict[str, Any]) -> str:
    """One old_string -> new_string replacement, as the Edit tool does it."""
    old = str(edit.get("old_string") or "")
    new = str(edit.get("new_string") or "")
    if old and old in text:
        return text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    # The CLI will reject this edit, but scan the new text anyway rather than drop it.
    return f"{text}\n{new}"


def _cell_source(cell: dict[str, Any]) -> str:
    """A notebook cell's source, which is a string or a list of lines."""
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _notebook_after_edit(current: str, tool_input: dict[str, Any]) -> str:
    """Every cell's source after a NotebookEdit, joined by newlines."""
    try:
        cells = json.loads(current).get("cells", []) if current.strip() else []
    except (json.JSONDecodeError, AttributeError):
        cells = [{"source": current}]  # not valid notebook JSON: scan the raw text
    cell_id = tool_input.get("cell_id")
    mode = tool_input.get("edit_mode") or "replace"
    removed_id = cell_id if mode in _REMOVING_MODES else None
    sources = [
        _cell_source(cell)
        for cell in cells
        if isinstance(cell, dict) and not (removed_id and cell.get("id") == removed_id)
    ]
    if mode != "delete":
        sources.append(str(tool_input.get("new_source") or ""))
    return "\n".join(sources)


def text_after_edit(tool_name: str, tool_input: dict[str, Any], path: Path) -> str:
    """The whole text of a file after an edit call is applied to it.

    Args:
        tool_name: "Edit", "MultiEdit" or "NotebookEdit".
        tool_input: The tool's input dict.
        path: The file, already resolved to an absolute path.

    Returns:
        The file's text after the edit (a notebook's cell sources, joined).

    Raises:
        OSError: The file exists but can't be read (fail_closed turns it into a deny).
    """
    current = _read_current(path)
    if tool_name == NOTEBOOK_EDIT:
        return _notebook_after_edit(current, tool_input)
    edits = tool_input.get("edits") if tool_name == MULTI_EDIT else [tool_input]
    for edit in edits or []:
        if isinstance(edit, dict):
            current = _apply_edit(current, edit)
    return current
