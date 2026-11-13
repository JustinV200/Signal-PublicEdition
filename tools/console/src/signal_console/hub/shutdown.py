"""Ask the voice hub to shut down cleanly, and wait for a process to exit.

audiohub's kernel server takes one request line, {"token", "command": "shutdown"},
and answers {"ok": true} before exiting the way Ctrl+C does: it restores ducked
or paused music and closes the audio and Claude. The wire format is audiohub's
(tools/audiohub/src/audiohub/kernel/ipc/README.md), spoken here without
importing audiohub so the tools stay independent. Stop sends it first and
kills the hub only if it hasn't exited after GRACEFUL_EXIT_TIMEOUT_S.
"""

import json
import logging
import socket
from pathlib import Path

import psutil

from signal_console.paths import HUB_PORT, HUB_TOKEN_PATH, LOOPBACK_HOST

logger = logging.getLogger(__name__)

SHUTDOWN_COMMAND = "shutdown"
CONNECT_TIMEOUT_S = 3.0
REPLY_TIMEOUT_S = 5.0
# audiohub's lines are capped at 16 KiB; its shutdown reply is a few bytes.
MAX_REPLY_BYTES = 16 * 1024
# Long enough for the hub to restore the music and close Claude, short enough for a click.
GRACEFUL_EXIT_TIMEOUT_S = 10.0


def request_hub_shutdown(token_path: Path = HUB_TOKEN_PATH, port: int = HUB_PORT) -> bool:
    """Ask the running hub to shut down cleanly.

    Args:
        token_path: The hub's IPC token file (it exists only while the hub listens).
        port: The hub's kernel port.

    Returns:
        True if the hub agreed, False if it isn't listening (still starting,
        or wedged) or didn't agree, in which case the caller kills it.
    """
    try:
        token = token_path.read_text(encoding="ascii").strip()
        reply = _exchange(port, {"token": token, "command": SHUTDOWN_COMMAND})
        agreed = json.loads(reply).get("ok") is True
    except (OSError, UnicodeDecodeError, ValueError, AttributeError) as error:
        # AttributeError: the reply was JSON but not an object.
        logger.info("voice hub didn't take a shutdown request: %r", error)
        return False
    if not agreed:
        logger.info("voice hub refused the shutdown request: %r", reply[:200])
    return agreed


def wait_for_exit(process: psutil.Process, timeout_s: float) -> bool:
    """True once `process` has exited, False if it's still running after timeout_s."""
    try:
        process.wait(timeout_s)
    except psutil.TimeoutExpired:
        return False
    return True


def _exchange(port: int, payload: dict[str, str]) -> bytes:
    """Send one request line to the hub's kernel server and return its reply line.

    Raises:
        OSError: The hub can't be reached or didn't reply in time.
    """
    line = json.dumps(payload).encode("utf-8") + b"\n"
    with socket.create_connection((LOOPBACK_HOST, port), timeout=CONNECT_TIMEOUT_S) as connection:
        connection.settimeout(REPLY_TIMEOUT_S)
        connection.sendall(line)
        with connection.makefile("rb") as stream:
            return stream.readline(MAX_REPLY_BYTES)
