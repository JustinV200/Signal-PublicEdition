"""Deletes expired temporary notes (`Watch for (until YYYY-MM-DD): ...`) before a run.

Expiry is done here, in code, so the model never has to judge dates. It runs before
the run's snapshot, so the guard never sees these deletions as the model's work.
A line with no date, or a date that isn't a real calendar date, is left alone.
"""

import contextlib
import logging
import os
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# The whole line is the note, so only lines that start with the marker count.
TEMP_NOTE = re.compile(r"Watch for \(until (\d{4}-\d{2}-\d{2})\):")


def _is_expired(line: str, today: date) -> bool:
    """True if line is a temporary note whose date is before today."""
    match = TEMP_NOTE.match(line)
    if not match:
        return False
    try:
        return date.fromisoformat(match.group(1)) < today
    except ValueError:
        return False


def expire_notes(life_dir: Path, relative_paths: list[str], today: date) -> list[str]:
    """Remove expired temporary notes from the given files (relative to life_dir).

    Lines split on LF only; kept lines are preserved byte for byte, and the write is
    atomic. Returns the removed lines, stripped, for the log. A file that can't be read
    or written is logged and skipped (never raises).
    """
    removed: list[str] = []
    for relative in relative_paths:
        path = life_dir / relative
        temp = path.with_name(path.name + ".tmp")
        try:
            # Split on \n only (keeping it), so a lone \r or U+2028 never splits a line.
            lines = re.split(r"(?<=\n)", path.read_bytes().decode("utf-8"))
            kept = [line for line in lines if not _is_expired(line, today)]
            if len(kept) == len(lines):
                continue
            # Atomic: a crash mid-write must not leave a half-written KB file.
            temp.write_bytes("".join(kept).encode("utf-8"))
            os.replace(temp, path)
        except (OSError, UnicodeDecodeError):
            # Don't leave a stray temp file in life/ (e.g. the README is open in Word).
            with contextlib.suppress(OSError):
                temp.unlink(missing_ok=True)
            log.exception("could not expire notes in %s", relative)
            continue
        removed += [line.strip() for line in lines if line not in kept]
        log.info("expired %d note(s) from %s", len(lines) - len(kept), relative)
    return removed
