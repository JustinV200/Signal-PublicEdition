"""PowerShell data files (schedule.psd1): one `Key = value` per line inside `@{ }`.

Values are 'strings', numbers, $true/$false, or @('a', 'b') arrays, all on one line.
"""

import re
from typing import Any

_LINE = re.compile(r"^([ \t]*)(\w+)([ \t]*)=[ \t]*(.*?)[ \t]*$", re.M)
_QUOTED = re.compile(r"'((?:[^']|'')*)'")


def _parse(raw: str) -> Any:
    """A psd1 value as Python: str, list of str, bool, int or float."""
    if raw.startswith("@("):
        return [m.group(1).replace("''", "'") for m in _QUOTED.finditer(raw)]
    if raw.startswith("'"):
        match = _QUOTED.match(raw)
        return match.group(1).replace("''", "'") if match else raw
    if raw.lower() in ("$true", "$false"):
        return raw.lower() == "$true"
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def entries(text: str) -> list[tuple[str, Any]]:
    """Every (key, value) line."""
    return [(m.group(2), _parse(m.group(4))) for m in _LINE.finditer(text)]


def read(text: str, key: str) -> Any:
    """The key's value, or None."""
    return dict(entries(text)).get(key)


def write(text: str, key: str, literal: str) -> str:
    """Replace the key's value in place, or add the key before the closing brace."""
    for match in _LINE.finditer(text):
        if match.group(2) == key:
            line = f"{match.group(1)}{key}{match.group(3)}= {literal}"
            return text[: match.start()] + line + text[match.end() :]
    head, brace, tail = text.rpartition("}")
    if not brace:
        raise ValueError("not a PowerShell data file (no closing brace)")
    return f"{head.rstrip()}\n    {key} = {literal}\n{brace}{tail}"


def literal(value: Any) -> str:
    """'text', @('a', 'b'), $true/$false, or the number."""
    if isinstance(value, bool):
        return "$true" if value else "$false"
    if isinstance(value, list):
        return "@(" + ", ".join(literal(str(v)) for v in value) + ")"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)
