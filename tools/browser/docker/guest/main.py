"""Guest entry point: the process that runs as user "edge" after the entrypoint.

Part of the docker backend's guest (refdocs/research/docker-browser.md section 3).
entrypoint.sh execs this through setpriv, with no capabilities. It hides its
own /proc files (its environment holds the relay token), takes its settings
out of the environment, starts Xvfb and Edge, and serves the relay until the
host stops using it, Edge or Xvfb dies, or Docker sends SIGTERM. When it
returns, docker-init (PID 1) exits and `--rm` removes the container.
"""

import asyncio
import ctypes
import logging
import os
import signal
import sys
from asyncio.subprocess import Process
from collections.abc import MutableMapping

import processes
import relay

logger = logging.getLogger("relay")

PR_SET_DUMPABLE = 4
MIN_TOKEN_CHARS = 32
EXIT_CHECK_INTERVAL_S = 1.0


def make_undumpable() -> None:
    """Leave this process's /proc files (environ included) readable by real root only.

    os.environ.pop doesn't erase /proc/<pid>/environ, and a process running as
    "edge" is otherwise readable by every other "edge" process, Edge included.
    A no-op off Linux, so the module can be imported by host-side tests.

    Raises:
        OSError: If prctl fails.
    """
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_DUMPABLE, 0) failed")


def take_settings(environ: MutableMapping[str, str]) -> tuple[str, str]:
    """Pop the token and resolver rules out of `environ`.

    Returns:
        (token, resolver_rules). The rules may be empty.

    Raises:
        SystemExit: If the token is missing or shorter than MIN_TOKEN_CHARS.
    """
    token = environ.pop("SIGNAL_RELAY_TOKEN", "")
    resolver_rules = environ.pop("SIGNAL_RESOLVER_RULES", "")
    environ.pop("SIGNAL_BLOCK_CIDRS", None)
    if len(token) < MIN_TOKEN_CHARS:
        raise SystemExit("SIGNAL_RELAY_TOKEN is missing or too short")
    return token, resolver_rules


async def run(token: str, resolver_rules: str) -> str:
    """Start the children and serve the relay. Returns why it stopped."""
    xvfb = edge = None
    try:
        xvfb = await processes.start_xvfb()
        edge = await processes.start_edge(resolver_rules)
        tracker = relay.ConnectionTracker()
        server = await relay.serve(token, tracker)
        logger.info("relay listening on port %d", relay.RELAY_PORT)
        async with server:
            return await _wait_for_exit(tracker, {"Xvfb": xvfb, "Edge": edge})
    finally:
        await processes.stop_all([edge, xvfb])


async def _wait_for_exit(tracker: relay.ConnectionTracker, children: dict[str, Process]) -> str:
    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signal_number, stop_requested.set)
    while not stop_requested.is_set():
        if tracker.idle_for_s() >= relay.IDLE_EXIT_S:
            return f"no authenticated connection for {relay.IDLE_EXIT_S:.0f} s"
        for name, child in children.items():
            if child.returncode is not None:
                return f"{name} exited with status {child.returncode}"
        try:
            await asyncio.wait_for(stop_requested.wait(), EXIT_CHECK_INTERVAL_S)
        except TimeoutError:
            continue
    return "stop signal"


def main() -> int:
    """Harden, read settings, run until done. The exit status ends the container."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    make_undumpable()
    token, resolver_rules = take_settings(os.environ)
    reason = asyncio.run(run(token, resolver_rules))
    logger.info("stopping: %s", reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
