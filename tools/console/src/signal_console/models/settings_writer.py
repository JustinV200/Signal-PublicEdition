"""Write the owner's next-session model or effort pick into .claude/settings.local.json.

The one place the console edits Claude Code settings, so it is fenced in:

- only the keys in ALLOWED_VALUES, each only to a listed value, or removed
  ("use my user settings");
- the file must already parse as a JSON object. A missing, unreadable or
  malformed file is refused, never replaced with {};
- just before the atomic write the file is read again, and the write goes
  ahead only if its bytes still match the first read (one retry, then refuse).
  A Claude Code write landing between that re-read and the replace can still
  be lost, so the old bytes are copied to a backup first.

write_json_atomic writes `indent=1`, so the first write reformats the file;
that's cosmetic.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_jsonstate import StateFileError, read_bytes_retrying, write_json_atomic
from signal_modelchoice import EFFORT_LEVELS, MODEL_ALIASES

ALLOWED_VALUES: dict[str, tuple[str, ...]] = {"model": MODEL_ALIASES, "effortLevel": EFFORT_LEVELS}
WRITE_ATTEMPTS = 2  # the first try plus one retry if the file changed under us


class SettingsWriteError(RuntimeError):
    """The pick wasn't written; the message says why, for the console to show."""


@dataclass(frozen=True)
class SettingsFiles:
    """The settings file and where its pre-write copy goes."""

    settings: Path
    backup: Path


def write_local_setting(files: SettingsFiles, key: str, value: str | None) -> None:
    """Set `key` to `value` in the settings file, or remove it when `value` is None.

    Args:
        files: The settings file and its backup path.
        key: "model" or "effortLevel".
        value: One of that key's ALLOWED_VALUES, or None to remove the key.

    Raises:
        SettingsWriteError: The key or value isn't allowed, the file is missing or
            doesn't parse as a JSON object, it kept changing, or it couldn't be written.
            The file is left untouched in every case.
    """
    allowed = ALLOWED_VALUES.get(key)
    if allowed is None:
        raise SettingsWriteError(f"can't update settings: {key!r} isn't a key the console writes")
    if value is not None and value not in allowed:
        raise SettingsWriteError(f"can't update settings: {value!r} isn't an allowed {key}")
    for _ in range(WRITE_ATTEMPTS):
        before = _read(files.settings)
        settings = _parse_object(before)
        updated = _with_value(settings, key, value)
        if updated == settings:
            return  # already set: don't reformat the file for nothing
        _back_up(files.backup, before)
        if _read(files.settings) == before:
            _write(files.settings, updated)
            return
    raise SettingsWriteError("can't update settings: the file kept changing; try again")


def _read(path: Path) -> bytes:
    try:
        return read_bytes_retrying(path)
    except OSError as error:
        raise SettingsWriteError(f"can't update settings: can't read {path.name}") from error


def _parse_object(raw: bytes) -> dict[str, Any]:
    try:
        settings = json.loads(raw)
    except (ValueError, RecursionError) as error:  # deep nesting overflows the parser
        raise SettingsWriteError("can't update settings: file doesn't parse") from error
    if not isinstance(settings, dict):
        raise SettingsWriteError("can't update settings: file isn't a JSON object")
    return settings


def _with_value(settings: dict[str, Any], key: str, value: str | None) -> dict[str, Any]:
    # A copy, so the caller can still compare it with what was read.
    updated = dict(settings)
    if value is None:
        updated.pop(key, None)
    else:
        updated[key] = value
    return updated


def _back_up(backup: Path, raw: bytes) -> None:
    try:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(raw)
    except OSError as error:
        raise SettingsWriteError(f"can't update settings: no backup ({error})") from error


def _write(path: Path, settings: dict[str, Any]) -> None:
    try:
        write_json_atomic(path, settings)
    except StateFileError as error:
        raise SettingsWriteError(f"can't update settings: {error}") from error
