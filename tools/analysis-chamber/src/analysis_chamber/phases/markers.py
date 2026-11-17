"""Marker lines agents put in their replies (`NAME: value`, or a bare `NAME` flag)."""

import re


def find_marker(text: str, name: str) -> str | None:
    """The value of the last `NAME: value` line in text, or None if there isn't one.

    Leading `*`, `` ` `` and spaces are tolerated, since models sometimes bold markers.
    """
    pattern = re.compile(rf"^[\s*`]*{re.escape(name)}[\s*`]*:[\s*`]*(.+?)[\s*`]*$", re.MULTILINE)
    matches = pattern.findall(text)
    return matches[-1] if matches else None


def has_flag(text: str, name: str) -> bool:
    """Whether text has a line that is just NAME (formatting chars aside)."""
    return any(line.strip(" *`\t") == name for line in text.splitlines())
