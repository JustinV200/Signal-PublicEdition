"""Parent side of signal_confirm: runs the dialog in a short-lived child process, reads the answer.

confirm() blocks the calling thread (safe from any thread, since the window
lives in another process); confirm_async() awaits the child without blocking
the event loop. Both fail closed: bad arguments, a child that can't start,
crashes, hangs past its deadline or prints anything but the allow token all
return False and log why.
"""

import asyncio
import contextlib
import logging
import subprocess
import sys
from collections.abc import Sequence

from signal_confirm.protocol import ALLOW_TOKEN, DENY_TOKEN, DialogRequest

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 120.0
DEFAULT_ARM_DELAY_S = 1.5
# Extra time for the child to start Python and Tk before the parent stops waiting.
CHILD_START_GRACE_S = 15.0
# -I (isolated mode): the child ignores PYTHON* variables and never imports from the cwd.
CHILD_COMMAND = (sys.executable, "-I", "-m", "signal_confirm")
# Stops a console window flashing up when a windowless daemon starts the child.
CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
STDERR_LOG_CHARS = 2000


def confirm(
    title: str,
    message: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    arm_delay_s: float = DEFAULT_ARM_DELAY_S,
) -> bool:
    """Ask the owner Allow/Deny and block until they answer or the dialog times out.

    Args:
        title: Window title (sanitized before display).
        message: Body text; "\\n" separates lines (each line is sanitized).
        timeout_s: Seconds before the dialog denies by itself.
        arm_delay_s: Seconds Allow stays disabled after the window appears.

    Returns:
        True only when the owner clicked Allow. Never raises: every failure is False.
    """
    payload = _encode_request(title, message, timeout_s, arm_delay_s)
    if payload is None:
        return False
    return run_child(CHILD_COMMAND, payload, timeout_s + CHILD_START_GRACE_S)


async def confirm_async(
    title: str,
    message: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    arm_delay_s: float = DEFAULT_ARM_DELAY_S,
) -> bool:
    """Like confirm(), but awaits the child process instead of blocking the thread.

    Cancelling the awaiting task closes the dialog (the child is killed).
    """
    payload = _encode_request(title, message, timeout_s, arm_delay_s)
    if payload is None:
        return False
    return await run_child_async(CHILD_COMMAND, payload, timeout_s + CHILD_START_GRACE_S)


def run_child(command: Sequence[str], payload: bytes, deadline_s: float) -> bool:
    """Run the dialog child to completion and read its answer.

    Args:
        command: The child's command line (CHILD_COMMAND in production).
        payload: The encoded DialogRequest, written to the child's stdin.
        deadline_s: Seconds before the child is killed and the answer is deny.

    Returns:
        True only for a clean exit that printed the allow token.
    """
    try:
        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            timeout=deadline_s,
            creationflags=CREATION_FLAGS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("Confirm dialog didn't answer within %.1f s; denying", deadline_s)
        return False
    except OSError:
        logger.exception("Couldn't start the confirm dialog; denying")
        return False
    return read_answer(completed.returncode, completed.stdout, completed.stderr)


async def run_child_async(command: Sequence[str], payload: bytes, deadline_s: float) -> bool:
    """Async run_child(): same arguments and result; cancelling the caller kills the child."""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=CREATION_FLAGS,
        )
    except (OSError, NotImplementedError):
        # NotImplementedError: this event loop can't run subprocesses (a Windows selector loop).
        logger.exception("Couldn't start the confirm dialog; denying")
        return False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), deadline_s)
    except TimeoutError:
        logger.error("Confirm dialog didn't answer within %.1f s; denying", deadline_s)
        _kill(process)
        await process.wait()
        return False
    except asyncio.CancelledError:
        # Nobody is waiting for the answer any more, so don't leave a live dialog behind.
        _kill(process)
        raise
    return read_answer(process.returncode, stdout, stderr)


def _kill(process: asyncio.subprocess.Process) -> None:
    """Kill the child, unless it has exited in the meantime."""
    with contextlib.suppress(ProcessLookupError):
        process.kill()


def read_answer(returncode: int | None, stdout: bytes, stderr: bytes) -> bool:
    """Turn the child's exit code and output into the owner's answer.

    Returns:
        True only when the child exited 0 and printed exactly the allow token.
    """
    if returncode != 0:
        error_text = stderr.decode(errors="replace")[-STDERR_LOG_CHARS:]
        logger.error("Confirm dialog failed (exit %s); denying. %s", returncode, error_text)
        return False
    answer = stdout.strip()
    if answer not in (ALLOW_TOKEN.encode(), DENY_TOKEN.encode()):
        logger.error("Confirm dialog printed an unexpected answer %r; denying", answer[:100])
    return answer == ALLOW_TOKEN.encode()


def _encode_request(title: str, message: str, timeout_s: float, arm_delay_s: float) -> bytes | None:
    """Validate and encode the request, or log and return None if it is invalid."""
    try:
        return DialogRequest(title, message, timeout_s, arm_delay_s).to_json()
    except (TypeError, ValueError):
        logger.exception("Invalid confirm request; denying without a dialog")
        return None
