"""Read a small JSON state file, and replace one atomically.

Writers hold the folder's state_lock; readers need none, since a write is a temp file then
os.replace, so a reader only ever sees a whole file.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from signal_jsonstate.lock import StateFileError

log = logging.getLogger(__name__)

REPLACE_ATTEMPTS = 5
REPLACE_RETRY_S = 0.02


def read_bytes_retrying(path: Path) -> bytes:
    """`path`'s bytes, retrying briefly while Windows has it mid-replace.

    os.replace onto a file leaves it delete-pending for a moment, and opening it then
    fails with PermissionError, so a lock-free reader retries like a writer does.

    Raises:
        FileNotFoundError: There's no such file.
        OSError: It couldn't be read, even after the retries.
    """
    for _ in range(REPLACE_ATTEMPTS - 1):
        try:
            return path.read_bytes()
        except PermissionError:
            time.sleep(REPLACE_RETRY_S)
    return path.read_bytes()  # the last try lets its error through


def read_json_object(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} if there's no file yet.

    Writes are atomic, so a malformed file can only come from a hand edit: it's
    logged and read as empty, and the next write replaces it.

    Raises:
        StateFileError: The file exists but couldn't be read.
    """
    try:
        payload = json.loads(read_bytes_retrying(path))
    except FileNotFoundError:
        return {}
    except (ValueError, RecursionError):  # deep nesting overflows the parser
        log.warning("%s isn't valid JSON; reading it as empty", path.name)
        return {}
    except OSError as error:
        raise StateFileError(f"can't read {path.name}: {error}") from error
    return payload if isinstance(payload, dict) else {}


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write `payload` to `path` through a temp file and os.replace.

    Raises:
        StateFileError: The file couldn't be written.
    """
    write_text_atomic(path, json.dumps(payload, indent=1))


def write_text_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` through a temp file and os.replace, creating its folder if
    missing (a fresh state folder, e.g. the whiteboard's .state/idle, may not exist yet).

    Raises:
        StateFileError: The file couldn't be written.
    """
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(text, encoding="utf-8")
        _replace(temp, path)
    except OSError as error:
        temp.unlink(missing_ok=True)
        raise StateFileError(f"can't write {path.name}: {error}") from error


def _replace(temp: Path, path: Path) -> None:
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            # Windows won't replace a file a reader has open; readers are quick.
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_RETRY_S)
