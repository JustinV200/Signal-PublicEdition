"""Public API of whiteboard.keynotes: the day's 2-4 AI-written lines for the board.

- `generate_keynotes` (generate.py): once a morning (or on demand, `whiteboard keynotes`),
  Claude reads the day's plan items and writes what matters most today and why.
- `read_keynotes` (store.py): what the idle and TODO views show, plain code, only for
  the date the file was written for; a stale or missing file shows nothing.
"""

from whiteboard.keynotes.generate import MODEL, KeynotesError, generate_keynotes, parse_lines
from whiteboard.keynotes.store import KEYNOTES_FILE, MAX_LINES, read_keynotes, write_keynotes

__all__ = [
    "KEYNOTES_FILE",
    "MAX_LINES",
    "MODEL",
    "KeynotesError",
    "generate_keynotes",
    "parse_lines",
    "read_keynotes",
    "write_keynotes",
]
