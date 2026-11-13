"""Marked values inside Markdown prose: `<!-- setting:key -->value<!-- /setting -->`.

For settings that live in a sentence rather than a `- Label: value` line, such as the
context-handoff threshold in AGENTS.md section 4. The markers are HTML comments, so the
rendered page shows only the value, and only marked values count (prose with `<...>`
slots or example hosts is never read as a placeholder).
"""

import re
from typing import Any

_MARKED = re.compile(r"<!-- setting:([\w.-]+) -->(.*?)<!-- /setting -->")


def read(text: str, key: str) -> str | None:
    """The marked value for `key`, or None when the text has no such marker."""
    for match in _MARKED.finditer(text):
        if match.group(1) == key:
            return match.group(2)
    return None


def write(text: str, key: str, literal: str) -> str:
    """Replace the value between `key`'s markers (every occurrence).

    Raises:
        ValueError: The text has no marker for `key` (prose can't be appended to safely).
    """
    if read(text, key) is None:
        raise ValueError(f"no <!-- setting:{key} --> marker to write")
    return _MARKED.sub(
        lambda m: (
            f"<!-- setting:{key} -->{literal}<!-- /setting -->" if m.group(1) == key else m[0]
        ),
        text,
    )


def entries(text: str) -> list[tuple[str, Any]]:
    """Every (key, value) marker."""
    return [(m.group(1), m.group(2)) for m in _MARKED.finditer(text)]


def literal(value: Any) -> str:
    """Plain text; a list is comma-separated."""
    return ", ".join(map(str, value)) if isinstance(value, list) else str(value)
