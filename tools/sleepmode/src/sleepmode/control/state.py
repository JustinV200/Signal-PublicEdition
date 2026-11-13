"""SleepState and its file, .state/state.json: whether sleep mode is on and what it did.

The keeper process watches this file to know when to stop, so it's written
atomically (a temp file, then os.replace) and never left half-written.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sleepmode.screens import METHODS, MonitorResult

log = logging.getLogger(__name__)

REPLACE_ATTEMPTS = 5
REPLACE_RETRY_S = 0.05


class StateFileError(ValueError):
    """The state file exists but can't be read as a SleepState."""


@dataclass(frozen=True)
class SleepState:
    """Sleep mode's state.

    Attributes:
        is_asleep: True while sleep mode is on.
        session_id: Names this sleep; the keeper started for it exits when it changes.
        since: When sleep mode last turned on.
        wake_at: The scheduled wake time, or None.
        night_sky: Whether the night sky was asked for.
        monitors: What was done to each display at the last sleep.
        keeper_pid: The keeper process's id, or None.
        keeper_created: That process's creation time (a FILETIME count), or None. With
            the pid it tells the keeper from a later process that reused its pid.
        woke_at: When sleep mode last turned off.
        woke_by: Why: "request", "schedule", "input", ...
        lighting: What the last sleep did to the RGB lights, one line per backend.
        notes: Problems worth telling the owner (e.g. the wake task couldn't be set).
    """

    is_asleep: bool
    session_id: str = ""
    since: datetime | None = None
    wake_at: datetime | None = None
    night_sky: bool = True
    monitors: tuple[MonitorResult, ...] = ()
    keeper_pid: int | None = None
    keeper_created: int | None = None
    woke_at: datetime | None = None
    woke_by: str | None = None
    lighting: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())


def save_state(path: Path, state: SleepState) -> None:
    """Write the state atomically.

    Raises:
        OSError: The file couldn't be written.
    """
    payload = asdict(state)
    for key in ("since", "wake_at", "woke_at"):
        value = getattr(state, key)
        payload[key] = value.isoformat(timespec="seconds") if value else None
    path.parent.mkdir(parents=True, exist_ok=True)
    # Per-process temp name: the keeper and the wake task may both write at once.
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            # Windows won't replace a file while another process (the keeper) is reading it.
            if attempt == REPLACE_ATTEMPTS - 1:
                temp.unlink(missing_ok=True)
                raise
            time.sleep(REPLACE_RETRY_S)


def load_state(path: Path) -> SleepState | None:
    """Read the state file.

    Returns:
        The state, or None if there's no file (sleep mode never ran).

    Raises:
        StateFileError: The file is malformed.
        OSError: The file couldn't be read (often briefly, while it's being replaced).
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (UnicodeDecodeError, ValueError) as error:
        raise StateFileError(f"can't read {path}: {error}") from error
    try:
        return _parse_state(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise StateFileError(f"{path} is malformed: {error}") from error


def load_state_quietly(path: Path) -> SleepState | None:
    """The state file, or None when it's missing or can't be read (logged, never raised).

    For sleep and wake, which carry on without it rather than fail.
    """
    try:
        return load_state(path)
    except (StateFileError, OSError) as error:
        log.warning("ignoring an unreadable state file: %s", error)
        return None


def _parse_state(payload: Any) -> SleepState:
    """Build a SleepState from the decoded JSON, checking every field's type."""
    if not isinstance(payload, dict):
        raise TypeError("the state isn't an object")
    return SleepState(
        is_asleep=_require(payload, "is_asleep", bool),
        session_id=_require(payload, "session_id", str),
        since=_parse_time(payload.get("since")),
        wake_at=_parse_time(payload.get("wake_at")),
        night_sky=_require(payload, "night_sky", bool),
        monitors=tuple(_parse_monitor(item) for item in payload.get("monitors", [])),
        keeper_pid=_optional(payload, "keeper_pid", int),
        keeper_created=_optional(payload, "keeper_created", int),
        woke_at=_parse_time(payload.get("woke_at")),
        woke_by=_optional(payload, "woke_by", str),
        lighting=tuple(str(line) for line in payload.get("lighting", [])),
        notes=tuple(str(note) for note in payload.get("notes", [])),
    )


def _parse_monitor(item: Any) -> MonitorResult:
    """Build one MonitorResult, checking the method and the rect."""
    if not isinstance(item, dict):
        raise TypeError("a monitor entry isn't an object")
    method = _require(item, "method", str)
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    rect = item["rect"]
    if not (isinstance(rect, list) and len(rect) == 4 and all(isinstance(n, int) for n in rect)):
        raise TypeError("rect isn't four integers")
    return MonitorResult(
        device_name=_require(item, "device_name", str),
        friendly_name=_require(item, "friendly_name", str),
        method=method,
        detail=_require(item, "detail", str),
        rect=(rect[0], rect[1], rect[2], rect[3]),
        is_projector=_require(item, "is_projector", bool),
    )


def _require[T](data: dict[str, Any], key: str, kind: type[T]) -> T:
    value = data[key]
    if not isinstance(value, kind):
        raise TypeError(f"{key} isn't a {kind.__name__}")
    return value


def _optional[T](data: dict[str, Any], key: str, kind: type[T]) -> T | None:
    value = data.get(key)
    if value is not None and not isinstance(value, kind):
        raise TypeError(f"{key} isn't a {kind.__name__}")
    return value


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("a time isn't a string")
    return datetime.fromisoformat(value)
