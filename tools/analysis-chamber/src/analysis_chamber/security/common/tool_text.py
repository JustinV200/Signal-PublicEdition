"""Pull the code a tool call will run or write out of its input, for the content hooks.

page_fetch_hook, shell_send_hook and personal_write_hook read shell commands (Bash and,
on headless Windows sessions, PowerShell) and the text of script files being written.
For an edit of an existing script that's the whole file after the edit (edits.py).
"""

from pathlib import Path, PurePath
from typing import Any

from analysis_chamber.security.common.code_paths import resolve_against
from analysis_chamber.security.common.edits import text_after_edit

# Headless Windows sessions get PowerShell, not Bash (tool-isolation spike, section 2).
SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
FILE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SCRIPT_SUFFIXES = frozenset({".py", ".ps1", ".psm1", ".sh", ".bash", ".bat", ".cmd", ".ipynb"})
# Scripts whose text is Python, not shell: no command lines, and `>` is a comparison.
PYTHON_SUFFIXES = frozenset({".py", ".ipynb"})

# Matcher strings for HookMatcher (regex alternation, as the CLI reads them).
SHELL_MATCHER = "|".join(sorted(SHELL_TOOLS))
SHELL_AND_WRITE_MATCHER = "|".join(sorted(SHELL_TOOLS | FILE_WRITE_TOOLS))


def written_path(tool_input: dict[str, Any]) -> str | None:
    """The target path of a Write/Edit/MultiEdit/NotebookEdit call, or None."""
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    return str(path) if path else None


def is_python_file(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Whether a call writes or edits a Python file (.py or .ipynb), whose text isn't shell."""
    path = written_path(tool_input) if tool_name in FILE_WRITE_TOOLS else None
    return path is not None and PurePath(path).suffix.lower() in PYTHON_SUFFIXES


def code_text(tool_name: str, tool_input: dict[str, Any], base_dir: Path) -> str | None:
    """The code a call runs (a shell command) or writes (into a script file), else None.

    Args:
        tool_name: The SDK tool name.
        tool_input: The tool's input dict.
        base_dir: Where relative file paths start (the run folder).

    Returns:
        The command, a Write's new script text, or the whole script after an edit;
        None for any other tool or file type.

    Raises:
        OSError: An edited script exists but can't be read.
    """
    if tool_name in SHELL_TOOLS:
        return str(tool_input.get("command") or "")
    if tool_name not in FILE_WRITE_TOOLS:
        return None
    path = written_path(tool_input)
    if path is None or PurePath(path).suffix.lower() not in SCRIPT_SUFFIXES:
        return None
    if tool_name == "Write":
        return str(tool_input.get("content") or "")
    return text_after_edit(tool_name, tool_input, resolve_against(path, base_dir))
