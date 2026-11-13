"""describe_tool_call: a short, readable description of a tool call for the approval dialog.

The CLI often supplies a full prompt sentence (ToolPermissionContext.title,
e.g. "Claude wants to read foo.txt"); when it does, that leads. The detail
line shows what will actually run or be touched (the command, file path or
URL), because the owner decides on that, not on the summary. Never raises,
whatever odd input Claude sends.
"""

import json
from collections.abc import Mapping

from claude_sessions.text import truncate

# Enough to read a whole typical command; the dialog stays a sensible size.
MAX_DETAIL_CHARS = 300
MAX_TITLE_CHARS = 160

# The input field that best shows what each tool will do.
_DETAIL_FIELDS = {
    "Bash": "command",
    "PowerShell": "command",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "Write": "file_path",
    "Read": "file_path",
    "NotebookEdit": "notebook_path",
    "WebFetch": "url",
    "WebSearch": "query",
    "Glob": "pattern",
    "Grep": "pattern",
    "Agent": "description",
    "Task": "description",
}


def describe_tool_call(
    tool_name: str, tool_input: Mapping[str, object], title: str | None = None
) -> str:
    """Describe a tool call in one or two short lines.

    Args:
        tool_name: The tool, e.g. "Bash" or "mcp__github__create_issue".
        tool_input: The tool's input as Claude sent it.
        title: The CLI's own prompt sentence, when it sent one.

    Returns:
        A headline (the CLI's title, or "Use <tool>"), then the detail on a
        second line when there is one.
    """
    headline = truncate(title, MAX_TITLE_CHARS) if title and title.strip() else f"Use {tool_name}"
    detail = _detail(tool_name, tool_input if isinstance(tool_input, Mapping) else {})
    return f"{headline}\n{detail}" if detail else headline


def _detail(tool_name: str, tool_input: Mapping[str, object]) -> str:
    """The most telling input field, or the whole input as compact JSON."""
    field_name = _DETAIL_FIELDS.get(tool_name)
    value = tool_input.get(field_name) if field_name else None
    if isinstance(value, str) and value.strip():
        return truncate(value, MAX_DETAIL_CHARS)
    if not tool_input:
        return ""
    try:
        compact = json.dumps(dict(tool_input), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        compact = repr(dict(tool_input))
    return truncate(compact, MAX_DETAIL_CHARS)
