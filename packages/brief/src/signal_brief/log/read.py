"""Read the event log and fold it: each key's last line wins.

Readers take no lock. An append is one write of one line, so the worst a reader
can see is a half-written last line, which is skipped like any malformed line.
"""

import json
import logging
from pathlib import Path

from signal_brief.log.entry import Entry, entry_from_payload
from signal_brief.paths import BriefPaths
from signal_brief.store import BriefLogError, read_bytes_retrying

log = logging.getLogger(__name__)


def read_log(path: Path) -> list[Entry]:
    """Every well-formed line of the log, in file order ([] if there's no log yet).

    Raises:
        BriefLogError: The log exists but couldn't be read.
    """
    try:
        text = read_bytes_retrying(path).decode("utf-8", errors="replace")
    except FileNotFoundError:
        return []
    except OSError as error:
        raise BriefLogError(f"can't read {path.name}: {error}") from error
    entries, skipped = [], 0
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            entry = entry_from_payload(json.loads(line))
        except ValueError:
            entry = None
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    if skipped:
        log.warning("skipped %d malformed line(s) in %s", skipped, path.name)
    return entries


def fold(entries: list[Entry]) -> dict[str, Entry]:
    """Each key's last line, keyed by key."""
    return {entry.key: entry for entry in entries}


def current_entries(paths: BriefPaths) -> list[Entry]:
    """The folded log, oldest seq first. Raises BriefLogError if unreadable."""
    return sorted(fold(read_log(paths.events)).values(), key=lambda entry: entry.seq)


def find_entry(entries: list[Entry], key_or_ref: str) -> Entry | None:
    """The entry with this ref (case-insensitive), else this key, else None.

    Refs win: they're what the owner sees, and a lowercase key like "w3" would
    otherwise shadow ref W3.
    """
    wanted = key_or_ref.strip()
    by_ref = next((entry for entry in entries if entry.ref == wanted.upper()), None)
    return by_ref or next((entry for entry in entries if entry.key == wanted), None)
