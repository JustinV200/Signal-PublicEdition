"""run_with_deadline: run one lighting step on a daemon thread and stop waiting at a deadline.

A hung OpenRGB server or vendor tool must never hold up sleep or wake, so every
backend call gets one overall deadline here. A step that overruns is abandoned, but
Python can't end a thread. Its daemon thread can't keep the process alive, yet in a
long-lived one (the MCP server) it runs on, and an openrgb-python call can spin for
good: when the server closes mid-reply, its read loop gets b"" from recv forever,
which no socket timeout ends. So on_timeout lets the caller stop it from outside:
Lighting abandons the step's StepGuard, which closes the step's socket (the stuck
recv then raises) and stops it before its next device change.
"""

import threading
from collections.abc import Callable


def run_with_deadline[T](
    work: Callable[[], T], timeout_s: float, name: str, *, on_timeout: Callable[[], None]
) -> T:
    """Run work() and return its result, or give up after timeout_s.

    Args:
        work: The step; it runs on its own daemon thread.
        timeout_s: How long to wait for it.
        name: Names the thread, for the log.
        on_timeout: Called when the deadline passes with work() still running, before
            TimeoutError is raised, to make the abandoned step stop (StepGuard.abandon).

    Raises:
        TimeoutError: work() was still running after timeout_s (on_timeout was called).
        Exception: Whatever work() raised.
    """
    results: list[T] = []
    errors: list[BaseException] = []

    def target() -> None:
        try:
            results.append(work())
        except BaseException as error:  # handed to the caller below, never lost
            errors.append(error)

    thread = threading.Thread(target=target, name=f"lighting-{name}", daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        on_timeout()
        raise TimeoutError(f"{name} took longer than {timeout_s:g} s")
    if errors:
        raise errors[0]
    return results[0]
