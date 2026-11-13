"""The shim's own stdio: a stdin reader thread and a flushing stdout line writer.

asyncio's connect_read_pipe is unreliable on Windows pipes, so a plain thread reads stdin
and hands each line to the event loop. stdout carries protocol lines only, as bytes.
"""

import logging
import sys
import threading
from collections.abc import Callable

log = logging.getLogger("mcpshim")


def start_stdin_reader(on_line: Callable[[bytes | None], None]) -> threading.Thread:
    """Read stdin lines on a daemon thread and pass each to `on_line`.

    Args:
        on_line: called from the reader thread with each line (line ending stripped,
            blank lines skipped), then once with None at EOF. It must be thread-safe,
            e.g. a loop.call_soon_threadsafe wrapper.

    Returns:
        The started thread.
    """

    def read_lines() -> None:
        try:
            for line in iter(sys.stdin.buffer.readline, b""):
                stripped = line.rstrip(b"\r\n")
                if stripped:
                    on_line(stripped)
        except OSError as error:
            log.error("stdin read failed: %s", error)
        on_line(None)

    thread = threading.Thread(target=read_lines, name="mcpshim-stdin", daemon=True)
    thread.start()
    return thread


def write_stdout_line(data: bytes) -> None:
    """Write one protocol line to stdout and flush it.

    A client that has gone away is only logged: its stdin EOF shuts the shim down.
    """
    try:
        sys.stdout.buffer.write(data + b"\n")
        sys.stdout.buffer.flush()
    except OSError as error:
        log.warning("stdout write failed: %s", error)
