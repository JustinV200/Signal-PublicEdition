"""The `console` log format, `serve`'s own copy of its log in .state/server.log, and
`open`'s printed output there when it has no console.

The logon task runs `serve` under pythonw, which has no stderr, so a server that
can't bind its port would fail without a trace unless it writes the file itself.
`console open` starts its server with stdout and stderr already going to
server.log, and then the file handler is left out so no line is written twice.
The Start-menu shortcut runs `open` under pythonw too, so its words go there as well.
"""

import logging
import os
import sys
from pathlib import Path

from signal_console.paths import SERVER_LOG_FILE
from signal_console.state_files import ensure_state_dir

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def log_to_server_log(state_dir: Path) -> None:
    """Also write this process's log records to `state_dir`/server.log.

    Does nothing when stderr already is that file (a server `console open` started),
    since the stderr handler writes every record there already.

    Raises:
        OSError: The state folder or the log file can't be made or opened.
    """
    ensure_state_dir(state_dir)
    path = state_dir / SERVER_LOG_FILE
    if _is_stderr(path):
        return
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(handler)


def print_to_server_log(state_dir: Path) -> None:
    """Send this process's printed output (stdout and stderr) to `state_dir`/server.log.

    For `console open` under pythonw (the Start-menu shortcut), which has no console,
    so its progress and its one-line error land beside the server's own log. The file
    is line-buffered, so these lines stay in order with the server's, and stays
    open until the process exits.

    Raises:
        OSError: The state folder or the log file can't be made or opened.
    """
    ensure_state_dir(state_dir)
    log_file = (state_dir / SERVER_LOG_FILE).open("a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log_file


def _is_stderr(path: Path) -> bool:
    try:
        return os.path.samestat(os.fstat(sys.stderr.fileno()), path.stat())
    except (AttributeError, OSError, ValueError):
        # No stderr (pythonw), one with no file behind it, or no log file yet.
        return False
