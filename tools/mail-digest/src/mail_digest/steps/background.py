"""`--now`: starts one run in the background and returns at once.

For on-demand runs: a voice session asking for a mail or assignment check shouldn't
block for the minutes a run takes. The background copy is `pythonw -m <module>`
(mail_digest for `mail-digest --now`, mail_digest.assignment_check for
`assignment-check --now`), the same foreground run, detached from the caller and with
no console. It takes the run lock like any other run. The digest and the checker
share that lock, since they edit the same files.
"""

import subprocess
import sys
from pathlib import Path

from mail_digest.memory import is_locked
from mail_digest.settings import LOG_PATH, REPO_ROOT

# Detached, in its own process group (the caller's Ctrl+C doesn't reach it), no window.
DETACHED_FLAGS = (
    getattr(subprocess, "DETACHED_PROCESS", 0)
    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
)


DIGEST_MODULE = "mail_digest"


def background_command(module: str = DIGEST_MODULE) -> list[str]:
    """`pythonw -m <module>` with this environment's pythonw (no console window)."""
    return [str(Path(sys.executable).with_name("pythonw.exe")), "-m", module]


def start_background_run(
    lock_path: Path,
    argv: list[str] | None = None,
    name: str = "mail digest",
    log_path: Path = LOG_PATH,
) -> int:
    """Start a detached run unless one is already going. Returns the exit code.

    argv: the command to start (default: background_command()). name and log_path:
    the run's name and log, for the one line printed for the caller either way.
    Raises OSError if the process can't start.
    """
    if is_locked(lock_path):
        print(
            f"A mail digest or assignment check is running; not starting the {name}. "
            "Try again in a minute.",
            file=sys.stderr,
        )
        return 1
    subprocess.Popen(
        argv or background_command(),
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
        close_fds=True,
    )
    print(f"Started the {name} in the background. Log: {log_path}")
    return 0
