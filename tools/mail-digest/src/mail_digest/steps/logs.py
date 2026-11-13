"""Logging for a runner's CLI: a rotating log file, plus stderr when there's a console.

The mail digest and the assignment checker each log to their own file in .state/.
A background run (pythonw) has no stderr, so it logs to the file only.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mail_digest.settings import LOG_BACKUP_COUNT, LOG_MAX_BYTES

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def setup_logging(log_path: Path) -> None:
    """Log INFO and up to log_path (rotating), and to stderr if there is one.

    Raises OSError if the log folder can't be made or the file can't be opened.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers, force=True)
