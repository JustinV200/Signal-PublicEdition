"""Typed setting values: parse what the user typed, and show a value back to them."""

import re
from typing import Any

TYPES = frozenset({"str", "int", "float", "bool", "list", "times"})
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_EMPTY_LIST = ("none", "[]")


def _items(text: str) -> list[str]:
    """Comma-separated items; 'none' or [] is the empty list."""
    if text.lower() in _EMPTY_LIST:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def parse(kind: str, text: str) -> Any:
    """`text` as a `kind` value. Raises ValueError with a message the user can act on."""
    text = text.strip()
    if kind == "int":
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError(f"{text!r} isn't a whole number")
        return int(text)
    if kind == "float":
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{text!r} isn't a number") from None
    if kind == "bool":
        if text.lower() not in ("yes", "no", "true", "false", "y", "n"):
            raise ValueError("type yes or no")
        return text.lower() in ("yes", "true", "y")
    if kind == "list":
        return _items(text)
    if kind == "times":
        times = _items(text)
        bad = [t for t in times if not _TIME.match(t)]
        if bad or not times:
            raise ValueError("give one or more 24-hour times like 07:00, 14:30")
        return times
    if not text:
        raise ValueError("the value can't be empty")
    return text


def display(value: Any) -> str:
    """A value as the user would type it back."""
    if value is None:
        return "(not set)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "none"
    return str(value)
