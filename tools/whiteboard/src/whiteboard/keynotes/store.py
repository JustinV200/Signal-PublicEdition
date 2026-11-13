"""The keynotes file, .state/keynotes.json: today's few lines, written once a morning.

Shape: {"date": "2026-10-25", "generated_at": "<ISO time>", "model": "sonnet",
"lines": ["...", ...]}. Readers only ever show it for the date it was written for:
a missing, unreadable, malformed or stale file reads as no keynotes, never an error,
so the views just leave the block out. Each line is cleaned (clean_text) and capped
on the way in and out, since the file could be edited by hand.
"""

import json
import logging
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path

from whiteboard.idle import clean_text
from whiteboard.shared import write_atomically

logger = logging.getLogger(__name__)

KEYNOTES_FILE = "keynotes.json"
MAX_LINES = 4
# The prompt asks for 48 (what fits the idle view's box); this is the hard cap kept.
MAX_LINE_CHARS = 80


def read_keynotes(path: Path, today: date) -> tuple[str, ...]:
    """Today's keynote lines, or () when the file is missing, bad or from another day.

    Args:
        path: The keynotes file.
        today: Lines written for any other date are not shown.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, ValueError, RecursionError) as error:
        logger.warning("keynotes: can't read %s (%s); showing none", path, error)
        return ()
    if not isinstance(data, dict) or data.get("date") != today.isoformat():
        return ()
    lines = data.get("lines")
    if not isinstance(lines, list):
        return ()
    return clean_lines(line for line in lines if isinstance(line, str))


def write_keynotes(path: Path, day: date, lines: Sequence[str], model: str) -> None:
    """Replace the keynotes file with `day`'s lines in one step.

    Raises:
        OSError: The file can't be written.
    """
    data = {
        "date": day.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": model,
        "lines": list(clean_lines(lines)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, json.dumps(data, indent=1, ensure_ascii=False).encode("utf-8"))


def clean_lines(lines: Iterable[str]) -> tuple[str, ...]:
    """Up to MAX_LINES non-empty lines, each one tidy line of at most MAX_LINE_CHARS."""
    cleaned = (clean_text(line, MAX_LINE_CHARS) for line in lines)
    return tuple(line for line in cleaned if line)[:MAX_LINES]
