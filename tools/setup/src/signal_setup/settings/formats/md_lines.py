"""Markdown settings: `- Label: value` list lines (the jobhunt runbook and profile).

The label is the key. Only `- ` lines with a colon count; everything else is prose.
"""

import re
from typing import Any

_LINE = re.compile(r"^- ([^:\n]+):[ \t]*(.*)$", re.M)


def read(text: str, key: str) -> str | None:
    """The text after `- key:`, or None when there's no such line."""
    for match in _LINE.finditer(text):
        if match.group(1).strip() == key:
            return match.group(2).strip()
    return None


def write(text: str, key: str, literal: str) -> str:
    """Replace the value on the `- key:` line, or append the line at the end."""
    for match in _LINE.finditer(text):
        if match.group(1).strip() == key:
            return f"{text[: match.start()]}- {key}: {literal}{text[match.end() :]}"
    return text.rstrip("\n") + f"\n- {key}: {literal}\n"


def entries(text: str) -> list[tuple[str, Any]]:
    """Every (label, value) list line."""
    return [(m.group(1).strip(), m.group(2).strip()) for m in _LINE.finditer(text)]


def literal(value: Any) -> str:
    """Plain text; a list is comma-separated and a bool is yes or no (prose-friendly)."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return ", ".join(map(str, value)) if isinstance(value, list) else str(value)
