"""Read-merge-write of one JSON config file that the user (or Claude Code) also edits.

The writers in writers.py send .mcp.json, .claude/settings.local.json and the user's own
~/.claude/settings.json through update_json_file, so a merge can't destroy what's there:

- a file that exists but isn't a JSON object is refused with one sentence, never replaced
  (check_object lets a caller refuse before writing any of its files);
- the new content is written to a temp file first; then the file is read again, and only if
  its bytes still match the first read are the old bytes copied to a backup (under .setup/)
  and the temp moved over the file. Otherwise it starts over once, then refuses;
- the move is one os.replace, so a crash mid-write leaves the old file whole.

A write by someone else landing between that re-read and the replace can still be lost; the
backup covers it. Same approach as the console's settings writer, its own code because the
tools stay standalone. read_object is the read-only look at such a file.
"""

import contextlib
import copy
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

WRITE_ATTEMPTS = 2  # the first try plus one retry if the file changed under us
OPEN_ATTEMPTS = 5  # Windows briefly refuses a file another process has open or is replacing
OPEN_RETRY_S = 0.02


class WiringError(RuntimeError):
    """A config file was left as it was; the message is one sentence for the user."""


def check_object(path: Path) -> None:
    """Raise WiringError unless `path` is missing or holds a JSON object (it reads only)."""
    _parse_object(path, _read(path))


def read_object(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} when it's missing, unreadable or not an object.

    For a file setup only looks at. A broken one counts as empty on purpose: Claude Code
    can't load anything from it either, so nothing in it is there.
    """
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, RecursionError):  # deep nesting overflows the parser
        return {}
    return data if isinstance(data, dict) else {}


def update_json_file(
    path: Path, backup: Path, merge: Callable[[dict[str, Any]], dict[str, Any]]
) -> dict[str, Any]:
    """Pass the JSON object in `path` (or {} when it's missing) through `merge` and save it.

    Nothing is written when `merge` changes nothing, so a second run keeps the file as is.

    Args:
        path: The config file.
        backup: Where its old bytes go before it's replaced.
        merge: Gets a copy of the file's object and returns the object to save.

    Returns:
        The object the file now holds.

    Raises:
        WiringError: The file isn't a JSON object, it kept changing or stayed busy, or it
            couldn't be read, backed up or written. The file is untouched in every case.
    """
    for _ in range(WRITE_ATTEMPTS):
        before = _read(path)
        current = _parse_object(path, before)
        updated = merge(copy.deepcopy(current))
        if updated == current:
            return current  # already as wanted: don't reformat the file
        if _replace_if_unchanged(path, backup, before, updated):
            return updated
    raise WiringError(
        f"{path} kept changing or was busy while setup wrote it, so setup left it alone; try again."
    )


def _retrying[T](action: Callable[[], T]) -> T:
    """`action()`, retried briefly on PermissionError (Claude Code reads these files too)."""
    for _ in range(OPEN_ATTEMPTS - 1):
        try:
            return action()
        except PermissionError:
            time.sleep(OPEN_RETRY_S)
    return action()  # the last try lets its error through


def _read(path: Path) -> bytes | None:
    """The file's bytes, or None when it doesn't exist."""
    try:
        return _retrying(path.read_bytes)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise WiringError(f"Setup couldn't read {path} ({error.strerror or error}).") from error


def _parse_object(path: Path, raw: bytes | None) -> dict[str, Any]:
    """`raw` as a JSON object ({} for a missing file). Raises WiringError otherwise."""
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):  # deep nesting overflows the parser
        data = None
    if not isinstance(data, dict):
        raise WiringError(f"{path} isn't a JSON object, so setup left it alone; fix it and retry.")
    return data


def _back_up(path: Path, backup: Path, raw: bytes) -> None:
    """Copy `path`'s old bytes to `backup`."""
    try:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(raw)
    except OSError as error:
        raise WiringError(f"Setup couldn't back up {path} ({error.strerror or error}).") from error


def _replace_if_unchanged(
    path: Path, backup: Path, before: bytes | None, data: dict[str, Any]
) -> bool:
    """Write `data` over `path` if it still holds `before`, backing `before` up first.

    The temp is written before the re-read, so only the small backup write sits between
    that check and the replace. Returns False, with the file untouched, when it changed
    since `before` or Windows refused the replace (another program had it open); the
    caller starts over.
    """
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
        if _read(path) != before:
            return False
        if before is not None:
            _back_up(path, backup, before)
        try:
            os.replace(temp, path)
        except PermissionError:
            time.sleep(OPEN_RETRY_S)  # give the other program a moment before the retry
            return False
        return True
    except OSError as error:
        raise WiringError(f"Setup couldn't write {path} ({error.strerror or error}).") from error
    finally:
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)  # gone already after a replace
