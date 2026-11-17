"""console_tasks: runs the console CLI's `tasks set|done` for a chamber run.

Part of analysis_chamber.notify. The console Tasks page is fed only through
that CLI (it validates ids and lengths), so this is a thin subprocess wrapper.
"""

import hashlib
import subprocess
from collections.abc import Callable
from pathlib import Path

from analysis_chamber.runs import Manifest

# Runs one argv from `cwd`; raises on a non-zero exit. Tests pass a fake.
RunCommand = Callable[[list[str], Path], None]

CONSOLE_CMD = [
    "uv", "run", "--project", "tools/console", "--frozen", "--no-sync", "console", "tasks",
]  # fmt: skip
TASK_PREFIX = "chamber-"
MAX_ID_CHARS = 40  # signal_tasks ID_PATTERN allows 40 characters
MAX_NAME_CHARS = 60  # signal_tasks MAX_NAME_CHARS
MAX_NEXT_CHARS = 140  # signal_tasks MAX_NEXT_CHARS
NAME_PREFIX = "Chamber: "
PERSONAL_NAME = "Chamber: personal run"  # the question stays off the Tasks page and board
HASH_CHARS = 6
COMMAND_TIMEOUT_S = 30


def run_command(argv: list[str], cwd: Path) -> None:
    """Run `argv` in `cwd`.

    Raises:
        subprocess.CalledProcessError: On a non-zero exit.
        subprocess.TimeoutExpired: If it takes longer than COMMAND_TIMEOUT_S.
    """
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True, timeout=COMMAND_TIMEOUT_S)


def task_id(run_id: str) -> str:
    """The console task id for a run: `chamber-<run id>`.

    Over the console's limit it becomes the first 33 characters, `-` and a 6-character
    hash of the full id, so long ids that differ only at the end stay distinct.
    """
    full = TASK_PREFIX + run_id.lower()
    if len(full) <= MAX_ID_CHARS:
        return full
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:HASH_CHARS]
    keep = MAX_ID_CHARS - HASH_CHARS - 1
    return f"{full[:keep].rstrip('-.')}-{digest}"


def set_args(manifest: Manifest, status: str) -> list[str]:
    """argv for `console tasks set`.

    The name is the question, cut to the console's limit, except for runs not confirmed
    non-personal, which show a generic name.
    """
    if manifest.personal is False:
        name = (NAME_PREFIX + " ".join(manifest.question.split()))[:MAX_NAME_CHARS]
    else:
        name = PERSONAL_NAME
    return [
        *CONSOLE_CMD, "set", task_id(manifest.id), "--name", name,
        "--pct", str(manifest.percent), "--status", status,
        "--next", manifest.phase.value[:MAX_NEXT_CHARS],
    ]  # fmt: skip


def done_args(run_id: str) -> list[str]:
    """argv for `console tasks done`."""
    return [*CONSOLE_CMD, "done", task_id(run_id)]


def remove_args(run_id: str) -> list[str]:
    """argv for `console tasks rm` (a failed or cancelled run isn't "done")."""
    return [*CONSOLE_CMD, "rm", task_id(run_id)]
