"""Which OS setup runs on, and the platform label each tool shows in the checklist.

A tool lists the platforms its code supports in data/tools.json. Only "windows" is
tested; "linux" means the code avoids Windows-only APIs but nobody has run it there.
"""

import sys
from pathlib import Path

from signal_setup.registry import Tool

WINDOWS = "windows"
LINUX = "linux"


def current() -> str:
    """'windows', 'linux', or sys.platform for anything else."""
    if sys.platform == "win32":
        return WINDOWS
    if sys.platform.startswith("linux"):
        return LINUX
    return sys.platform


def label(tool: Tool) -> str:
    """The checklist label: 'Windows' or 'Windows + Linux (untested)'."""
    return "Windows + Linux (untested)" if LINUX in tool.platforms else "Windows"


def is_supported(tool: Tool, platform: str | None = None) -> bool:
    """True if `tool` lists `platform` (default: this OS)."""
    return (platform or current()) in tool.platforms


def venv_python(root: Path, tool_id: str, platform: str | None = None) -> str:
    """The tool's venv Python as a forward-slash path (backslashes break hook commands)."""
    venv = root / "tools" / tool_id / ".venv"
    on_windows = (platform or current()) == WINDOWS
    exe = venv / "Scripts" / "python.exe" if on_windows else venv / "bin" / "python"
    return exe.as_posix()
