"""`StatusLine`: one timestamped console line per state change of the voice loop.

The owner watches these to see what the hub is doing: listening, what it
heard, thinking, speaking. The `listen` command uses the same format.
Example: `[14:02:15.2] heard: "Hey Claude, what's the time?" (2.1 s audio, stt 85 ms)`
"""

import sys
from collections.abc import Callable
from datetime import datetime
from typing import TextIO

# Longest quoted text shown on one status line.
MAX_QUOTE_CHARS = 90
_ELLIPSIS = "..."
MS_PER_SECOND = 1000


class StatusLine:
    """Prints status lines, skipping a line identical to the one before it."""

    def __init__(
        self,
        stream: TextIO | None = None,
        clock: Callable[[], datetime] = datetime.now,
        on_show: Callable[[str, str], None] | None = None,
    ) -> None:
        """Create a printer.

        Args:
            stream: Where to print; None means whatever sys.stdout is at the time.
            clock: Returns the current time for the timestamp (tests pass a fixed one).
            on_show: Also gets `(label, detail)` of every printed line, e.g. to
                show the state on the phone page.
        """
        self._stream = stream
        self._clock = clock
        self._on_show = on_show
        self._last_line: str | None = None

    def show(self, label: str, detail: str = "") -> None:
        """Print `[HH:MM:SS.t] label: detail` unless it repeats the previous line.

        Args:
            label: The state, e.g. "listening" or "heard".
            detail: Optional extra text after a colon.
        """
        line = f"{label}: {detail}" if detail else label
        if line == self._last_line:
            return
        self._last_line = line
        stamp = self._clock().strftime("%H:%M:%S.%f")[:-5]
        stream = self._stream or sys.stdout
        print(_encodable(f"[{stamp}] {line}", stream), file=stream, flush=True)
        if self._on_show is not None:
            self._on_show(label, detail)


def quote(text: str, max_chars: int = MAX_QUOTE_CHARS, *, keep_end: bool = False) -> str:
    """Put text in double quotes on one line, shortened to `max_chars` with "...".

    Args:
        text: Any text; runs of whitespace (newlines too) become single spaces.
        max_chars: Longest text kept inside the quotes.
        keep_end: Shorten from the front instead, keeping the last words.
    """
    flat = " ".join(text.split())
    kept_chars = max_chars - len(_ELLIPSIS)
    if len(flat) > max_chars:
        if keep_end:
            flat = _ELLIPSIS + flat[-kept_chars:].lstrip()
        else:
            flat = flat[:kept_chars].rstrip() + _ELLIPSIS
    return f'"{flat}"'


def format_duration(seconds: float) -> str:
    """Format a duration for a status line: "85 ms" under a second, else "6.6 s"."""
    if seconds < 1:
        return f"{seconds * MS_PER_SECOND:.0f} ms"
    return f"{seconds:.1f} s"


def _encodable(line: str, stream: TextIO) -> str:
    # A console or pipe with a narrow code page (cp1252) can't print every
    # character Claude writes (emoji); replace those rather than crash.
    encoding = getattr(stream, "encoding", None) or "utf-8"
    return line.encode(encoding, errors="replace").decode(encoding)
