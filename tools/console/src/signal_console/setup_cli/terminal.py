"""Open the owner's own terminal on one tool's setup, for steps the wizard can't run.

Some steps take a password, a Windows Hello prompt or a typed client ID, so they only
run in an interactive terminal (`"terminal": true` in the registry). The wizard's
"Open a terminal" button starts a new PowerShell window running `setup.ps1 <tool>`:
a fixed program and script, with only a checked tool id added.
"""

import os
import subprocess
import sys
from pathlib import Path

from signal_console.launch import clean_env
from signal_console.setup_cli.requests import SetupRequestError, check_registry_id

CREATE_NEW_CONSOLE = 0x00000010
SETUP_SCRIPT = "setup.ps1"


def terminal_command(repo_root: Path, tool_id: str) -> list[str]:
    """The PowerShell command line that runs one tool's setup and stays open after."""
    tool = check_registry_id({"tool": tool_id}, "tool")
    script = str(repo_root / SETUP_SCRIPT)
    return ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", script, tool]


def open_terminal(repo_root: Path, tool_id: str) -> None:
    """Start a visible terminal window on the tool's setup.

    Raises:
        SetupRequestError: A bad tool id, or not on Windows (the window is Windows-only).
        OSError: PowerShell couldn't be started.
    """
    command = terminal_command(repo_root, tool_id)
    if sys.platform != "win32":
        raise SetupRequestError(f"run ./setup.sh {tool_id} in your terminal")
    subprocess.Popen(
        command,
        cwd=repo_root,
        env=clean_env(os.environ),
        creationflags=CREATE_NEW_CONSOLE,
        close_fds=True,
    )
