"""Persist Ducker's captured volumes so a crash mid-duck can be undone later.

The JSON file maps an app id (the session identifier, which has no process
id, so it survives an app restart) to its volume before ducking and the
ducked target:

    {"<app id>": {"original": 0.8, "ducked": 0.12}}

Ducker writes the file before any fade starts and removes entries once
they're restored (see ducker.py for when leftovers are recovered).

Persistence is a safety net, so file errors are logged and never stop ducking.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMP_SUFFIX = ".tmp"


@dataclass(frozen=True)
class SavedVolume:
    """One app's volume before ducking, and the level ducking faded it to."""

    original: float
    ducked: float


def load_saved_volumes(path: Path) -> dict[str, SavedVolume]:
    """Return the saved volumes, keyed by app id ({} if none).

    A file that can't be read or parsed, or holds invalid volumes, is logged,
    deleted (when unparsable), and treated as empty.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError):
        logger.warning("could not read ducking state %s; ignoring it", path, exc_info=True)
        return {}
    volumes = _parse_volumes(text)
    if volumes is None:
        logger.warning("ducking state %s is invalid; deleting it", path)
        delete_saved_volumes(path)
        return {}
    return volumes


def save_volumes(path: Path, volumes: dict[str, SavedVolume]) -> None:
    """Write the volumes atomically (temp file, then rename). Logs on failure."""
    data = {
        app_id: {"original": saved.original, "ducked": saved.ducked}
        for app_id, saved in volumes.items()
    }
    temp_path = path.with_name(path.name + TEMP_SUFFIX)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, path)
    except OSError:
        logger.warning("could not save ducking state to %s", path, exc_info=True)


def delete_saved_volumes(path: Path) -> None:
    """Remove the state file if it exists. Logs on failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("could not delete ducking state %s", path, exc_info=True)


def _parse_volumes(text: str) -> dict[str, SavedVolume] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    volumes: dict[str, SavedVolume] = {}
    for app_id, entry in data.items():
        saved = _parse_entry(entry)
        if saved is None:
            return None
        volumes[app_id] = saved
    return volumes


def _parse_entry(entry: Any) -> SavedVolume | None:
    if not isinstance(entry, dict):
        return None
    original, ducked = entry.get("original"), entry.get("ducked")
    if not (_is_volume(original) and _is_volume(ducked)):
        return None
    return SavedVolume(float(original), float(ducked))


def _is_volume(value: Any) -> bool:
    # NaN fails the range check because every comparison with NaN is False.
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    return is_number and 0.0 <= value <= 1.0
