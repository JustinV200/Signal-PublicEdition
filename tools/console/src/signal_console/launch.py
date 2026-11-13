"""Start a background process that outlives its starter: no window, own group, clean environment.

Used to start the console server (`console open`) and the voice hub
(`console hub start`). Both are often run from the orchestrator's Bash tool,
whose job object and Claude Code variables they must not inherit.

Process flags as in tools/sessions' ipc/launcher.py: CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP, trying CREATE_BREAKAWAY_FROM_JOB first so the child
leaves the starter's job object (which may kill the tree when the starter
exits); jobs that forbid breakaway refuse it, and then it starts without.
"""

import logging
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000
DETACHED_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

# Variables a parent Claude Code session sets for its children (as in tools/mail-digest's
# child_env.py). Passed on, they make the child act as that session's child: its inbox
# token, its session id. TODO: share one copy in packages/ with mail-digest.
INHERITED_SESSION_VARS = ("CLAUDECODE", "CLAUDE_PID", "MCP_CONNECTION_NONBLOCKING")
INHERITED_SESSION_PREFIXES = ("CLAUDE_CODE_", "CLAUDE_AGENT_SDK_")

log = logging.getLogger(__name__)


def clean_env(environ: Mapping[str, str]) -> dict[str, str]:
    """A copy of environ without a parent Claude session's variables."""
    return {
        name: value
        for name, value in environ.items()
        if name not in INHERITED_SESSION_VARS and not name.startswith(INHERITED_SESSION_PREFIXES)
    }


def spawn_detached(
    command: list[str], cwd: Path, log_file: BinaryIO, env: Mapping[str, str]
) -> subprocess.Popen[bytes]:
    """Start `command` in the background with stdout and stderr going to `log_file`.

    Args:
        command: The program and its arguments (no shell).
        cwd: Its working folder.
        log_file: An open binary file for its output.
        env: Its environment (usually clean_env(os.environ) plus extras).

    Returns:
        The started process.

    Raises:
        OSError: It couldn't be started.
    """
    try:
        return _popen(command, cwd, log_file, env, DETACHED_FLAGS | CREATE_BREAKAWAY_FROM_JOB)
    except PermissionError:
        log.info("Job object refused breakaway; starting %s inside it", command[0])
        return _popen(command, cwd, log_file, env, DETACHED_FLAGS)


def _popen(
    command: list[str], cwd: Path, log_file: BinaryIO, env: Mapping[str, str], flags: int
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        close_fds=True,
    )
