"""The hub's own pid record, `.cache/hub.json`, so the console can stop a hub it didn't start.

`audiohub run` writes it once its kernel IPC port is bound (a second hub that
fails to bind never touches it) and removes it on a clean exit, but only while
it still names this process. The console reads it in its `hub stop`
(tools/console/src/signal_console/hub/process.py), checking the pid and start
time against psutil so a reused pid is never taken for the hub. Readers never
delete it: a stale record reads as not running, and the next hub overwrites it.
"""

import contextlib
import json
import logging
import os
from pathlib import Path

import psutil

from audiohub.config import CACHE_DIR
from audiohub.kernel import restrict_to_current_user

logger = logging.getLogger(__name__)

HUB_RECORD_PATH = CACHE_DIR / "hub.json"
OWNER_ONLY_MODE = 0o600


def record_hub(stack: contextlib.AsyncExitStack, path: Path | None) -> None:
    """Write the record and have `stack` remove it on the way out (None: record nothing).

    Call it only once the IPC port is bound: a second hub that fails to bind
    never gets here, so it can't overwrite the running hub's record.

    Raises:
        OSError: The record couldn't be written.
    """
    if path is None:
        return
    write_hub_record(path)
    stack.callback(remove_hub_record, path)


def write_hub_record(path: Path) -> None:
    """Record this process's pid and start time at `path`, owner-only and atomically.

    The record is written to a temp file beside it, locked down, then moved
    over the old one, so a reader never sees half a record.

    Raises:
        OSError: The record couldn't be written.
    """
    me = psutil.Process()
    record = {"pid": me.pid, "create_time": me.create_time()}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{me.pid}.tmp")
    temp_path.unlink(missing_ok=True)  # a fresh file gets fresh permissions
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, OWNER_ONLY_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(record, file)
    if os.name == "nt":
        restrict_to_current_user(temp_path)
    os.replace(temp_path, path)


def remove_hub_record(path: Path) -> None:
    """Delete the record, unless another hub has since replaced it (or it isn't readable).

    Never raises: it runs on the way out, where a failure must not hide the real exit reason.
    """
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        logger.exception("could not read the hub record %s; leaving it", path)
        return
    if not isinstance(record, dict) or record.get("pid") != os.getpid():
        return
    try:
        path.unlink()
    except OSError:
        logger.exception("could not remove the hub record %s", path)
