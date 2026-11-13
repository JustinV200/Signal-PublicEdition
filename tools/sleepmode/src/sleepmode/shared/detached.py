"""popen_detached: start a background process that outlives whatever started it.

Used for the keeper (sleepmode.keeper), OpenRGB's SDK server (sleepmode.lighting)
and the whiteboard daemon (sleepmode.whiteboard_link). Like the sessions daemon
(tools/sessions ipc/launcher.py), it tries CREATE_BREAKAWAY_FROM_JOB first, so the
process isn't ended with the MCP server or terminal's job, and stays in the job when the
job doesn't allow breakaway.
"""

import logging
import subprocess
from pathlib import Path
from typing import BinaryIO

log = logging.getLogger(__name__)


def popen_detached(
    command: list[str] | str, flags: int, cwd: Path, output: BinaryIO | None = None
) -> subprocess.Popen[bytes]:
    """Start command with no inherited handles and its streams on NUL (or output).

    Args:
        command: An argv list, or a full command line (for cmd.exe's own quoting).
        flags: Windows creation flags (CREATE_NO_WINDOW, DETACHED_PROCESS, ...);
            CREATE_BREAKAWAY_FROM_JOB is added when the job allows it.
        cwd: The working directory.
        output: An open binary file for stdout and stderr; None sends them to NUL.

    Raises:
        OSError: The process couldn't be started.
    """
    try:
        return _popen(command, flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, cwd, output)
    except PermissionError:
        log.info("job object refused breakaway; starting %s inside it", _name(command))
        return _popen(command, flags, cwd, output)


def _popen(
    command: list[str] | str, flags: int, cwd: Path, output: BinaryIO | None
) -> subprocess.Popen[bytes]:
    # No inherited handles: an inherited log handle wouldn't append, so the child would
    # write over other processes' log lines. An explicit output file is only safe for a
    # child that is that file's one writer (the whiteboard daemon and its daemon.log).
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL if output is None else output,
        stderr=subprocess.DEVNULL if output is None else subprocess.STDOUT,
        creationflags=flags,
        close_fds=True,
    )


def _name(command: list[str] | str) -> str:
    return command if isinstance(command, str) else command[0]
