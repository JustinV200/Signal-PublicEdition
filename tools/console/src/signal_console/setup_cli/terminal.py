"""Open the owner's own terminal on one setup step, for steps the wizard can't run.

Some steps take a password, a Windows Hello prompt or a typed client ID, so they only
run in an interactive terminal (`"terminal": true` in the registry). The wizard's
"Open a terminal" button starts a new PowerShell window running
`setup.ps1 step <tool> <step>`: that one step and nothing else (no wiring). It's a fixed
program and script with only checked ids added, and the secret is typed into that window,
so it never passes through the page or this server.
"""

import os
import subprocess
import sys
from pathlib import Path

from signal_console.launch import clean_env
from signal_console.setup_cli.requests import SetupRequestError, check_registry_id

CREATE_NEW_CONSOLE = 0x00000010
SETUP_SCRIPT = "setup.ps1"
STEP_COMMAND = "step"


def terminal_command(repo_root: Path, tool_id: str, step_id: str) -> list[str]:
    """The PowerShell command line that runs one setup step and stays open after.

    -NoExit keeps the window open after setup.ps1's `exit`, so the owner can read the
    result (checked: Windows PowerShell 5.1 runs `-File` scripts and stays open).
    The ids are checked by shape here; the setup CLI then refuses one its registry
    doesn't have (exit 2, in that window) before anything runs.

    Raises:
        SetupRequestError: A tool or step id of the wrong shape.
    """
    ids = {"tool": tool_id, "step": step_id}
    tool, step = check_registry_id(ids, "tool"), check_registry_id(ids, "step")
    script = str(repo_root / SETUP_SCRIPT)
    shell = ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", script]
    return [*shell, STEP_COMMAND, tool, step]


def open_terminal(repo_root: Path, tool_id: str, step_id: str) -> None:
    """Start a visible terminal window on one setup step.

    Raises:
        SetupRequestError: A bad tool or step id, or not on Windows (the window is
            Windows-only).
        OSError: PowerShell couldn't be started.
    """
    command = terminal_command(repo_root, tool_id, step_id)
    if sys.platform != "win32":
        raise SetupRequestError(
            f"run ./setup.sh {STEP_COMMAND} {tool_id} {step_id} in your terminal"
        )
    subprocess.Popen(
        command,
        cwd=repo_root,
        env=clean_env(os.environ),
        creationflags=CREATE_NEW_CONSOLE,
        close_fds=True,
    )
