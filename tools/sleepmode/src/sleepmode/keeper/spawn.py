"""Start the keeper process in the background.

The keeper is `python -m sleepmode keeper ...` from the same venv. It gets
CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP, and sleepmode.shared.popen_detached adds
CREATE_BREAKAWAY_FROM_JOB when it can, so it outlives the MCP server or terminal that
started it. A keeper that dies straight away (a crash at import, say) counts as a
failed start, so sleep never reports success with no keeper. A start that fails or is
interrupted after the process exists ends that process, so no keeper is left up that
no state names.
"""

import logging
import subprocess
import sys
from dataclasses import dataclass

from sleepmode.config import TOOL_ROOT
from sleepmode.shared import popen_detached, process_creation_time

log = logging.getLogger(__name__)

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
KEEPER_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP


@dataclass(frozen=True)
class KeeperOptions:
    """What one keeper does.

    Attributes:
        session_id: The sleep it belongs to; it exits when the state file names another.
        rects: Black windows to show, as physical (x, y, width, height); never the projector.
        keep_display_on: Hold the displays on too (while the projector is in use).
        grace_s: Seconds of ignored input after it starts.
        projector: The projector's rect, which the keeper keeps dark (night_guard), or None.
        night_sky: What the keeper asks the whiteboard for: the sky, or a black page.
    """

    session_id: str
    rects: tuple[tuple[int, int, int, int], ...]
    keep_display_on: bool
    grace_s: float
    projector: tuple[int, int, int, int] | None = None
    night_sky: bool = True


def keeper_command(options: KeeperOptions, python: str = sys.executable) -> list[str]:
    """The keeper's command line (parsed back by `sleepmode keeper`)."""
    command = [
        python,
        "-m",
        "sleepmode",
        "keeper",
        "--session",
        options.session_id,
        f"--grace={options.grace_s:g}",
    ]
    if options.keep_display_on:
        command.append("--keep-display-on")
    if options.night_sky:
        command.append("--night-sky")
    # The "=" form keeps a negative x (a display left of the primary) from reading as a flag.
    command += [f"--blackout={_rect_text(rect)}" for rect in options.rects]
    if options.projector is not None:
        command.append(f"--projector={_rect_text(options.projector)}")
    return command


def _rect_text(rect: tuple[int, int, int, int]) -> str:
    return ",".join(str(value) for value in rect)


@dataclass(frozen=True)
class KeeperProcess:
    """A running keeper, as recorded in the state file.

    Attributes:
        pid: The venv launcher's pid (ending it ends the keeper; see keeper.process).
        created: That launcher's creation time (process_creation_time), so a reused
            pid is never mistaken for it.
    """

    pid: int
    created: int


def start_keeper(options: KeeperOptions, startup_check_s: float) -> KeeperProcess:
    """Start the keeper detached, and make sure it's still running startup_check_s later.

    It writes its own log (sleepmode.cli), so no output is kept.

    Args:
        options: What the keeper does.
        startup_check_s: How long it must stay up to count as started.

    Returns:
        The keeper's pid and creation time.

    Raises:
        OSError: The process couldn't be started, or it exited within startup_check_s.
            Any failure once it exists (Ctrl+C included) ends it before propagating.
    """
    # A fixed command: our own interpreter running our own module.
    process = popen_detached(keeper_command(options), KEEPER_FLAGS, TOOL_ROOT)
    try:
        return _check_started(process, startup_check_s)
    except BaseException:
        # A failed check, or Ctrl+C during it: the caller never gets this pid, so no state
        # will name the keeper and nothing else could end it if it hung on. Popen's handle
        # makes this the keeper for sure (never a reused pid); a no-op if it already exited.
        process.kill()
        raise


def _check_started(process: subprocess.Popen[bytes], startup_check_s: float) -> KeeperProcess:
    """The keeper's pid and creation time once it has stayed up startup_check_s.

    Raises:
        OSError: It exited within startup_check_s, or its creation time can't be read.
    """
    try:
        code = process.wait(timeout=startup_check_s)
    except subprocess.TimeoutExpired:
        # Still up. Popen holds its handle, so the pid can't have been reused yet.
        keeper = KeeperProcess(process.pid, process_creation_time(process.pid))
        log.info("keeper started (pid %d)", keeper.pid)
        return keeper
    raise OSError(f"the keeper exited straight away (exit code {code}); see .state/sleepmode.log")
