"""SessionStore: persists managed-session records to `.state/sessions.json`.

Writes are atomic (temp file + replace), so a crash mid-write never leaves a
half-written file. A file that can't be read is moved aside, not overwritten,
so the owner can inspect it; single bad records are skipped with a warning.
Only the newest MAX_STORED_SESSIONS records (plus any older live ones) are
written, as compact JSON, so the file stays small however long the daemon runs.
"""

import json
import logging
import os
import time
from collections.abc import Iterable
from pathlib import Path

from claude_sessions.daemon.session.record import SessionRecord, SessionState

logger = logging.getLogger(__name__)

FILE_VERSION = 1
ENCODING = "utf-8"
CORRUPT_SUFFIX = ".corrupt"
TEMP_SUFFIX = ".tmp"
# Older finished records are dropped on save; their transcripts stay in ~/.claude/projects.
MAX_STORED_SESSIONS = 100
_FINISHED_STATES = frozenset({SessionState.STOPPED, SessionState.ERROR})


class SessionStore:
    """Loads and saves all session records as one JSON file."""

    def __init__(self, path: Path) -> None:
        """Use the file at path; its folder is created on the first save.

        Args:
            path: Normally config.sessions_file(settings.state_dir).
        """
        self._path = path

    def load(self) -> list[SessionRecord]:
        """Read every record.

        Returns:
            The records, or [] when the file doesn't exist yet or can't be read
            (in which case it is moved aside and the error logged).
        """
        try:
            raw = self._path.read_text(encoding=ENCODING)
        except FileNotFoundError:
            return []
        try:
            entries = _entries(json.loads(raw))
        except (json.JSONDecodeError, ValueError) as error:
            self._move_aside(error)
            return []
        return [record for entry in entries if (record := _record_or_none(entry)) is not None]

    def save(self, records: Iterable[SessionRecord]) -> None:
        """Replace the file with these records.

        Args:
            records: Every record the daemon knows; finished ones past the
                newest MAX_STORED_SESSIONS are left out.

        Raises:
            OSError: The file couldn't be written.
        """
        newest_first = sorted(records, key=lambda record: record.updated_at, reverse=True)
        kept = [
            record
            for index, record in enumerate(newest_first)
            if index < MAX_STORED_SESSIONS or record.state not in _FINISHED_STATES
        ]
        payload = {"version": FILE_VERSION, "sessions": [record.to_json() for record in kept]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_name(self._path.name + TEMP_SUFFIX)
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        temp_path.write_text(text, encoding=ENCODING)
        os.replace(temp_path, self._path)

    def _move_aside(self, error: Exception) -> None:
        """Keep an unreadable file for inspection instead of silently overwriting it."""
        aside = self._path.with_name(f"{self._path.name}{CORRUPT_SUFFIX}-{int(time.time())}")
        logger.error(
            "Can't read %s (%s); moved it to %s and starting empty", self._path, error, aside
        )
        os.replace(self._path, aside)


def _entries(data: object) -> list[object]:
    """The list of record objects in a decoded file."""
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise ValueError('expected an object with a "sessions" list')
    return data["sessions"]


def _record_or_none(entry: object) -> SessionRecord | None:
    """One record, or None (with a warning) when it is malformed."""
    try:
        return SessionRecord.from_json(entry)
    except ValueError as error:
        logger.warning("Skipping a bad record in the sessions file: %s", error)
        return None
