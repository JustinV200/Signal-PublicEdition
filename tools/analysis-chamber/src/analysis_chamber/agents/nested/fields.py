"""Python-side checks for nested sessions' structured output.

The CLI already holds the model to the JSON schema, but its output is derived
from untrusted text, so every field is re-checked here: wrong types are dropped,
strings are cut to a limit, unknown keys never pass. Only what survives reaches
the lead.
"""

from typing import Any


class NestedError(Exception):
    """A nested session failed, timed out or returned output that doesn't validate."""


def clip(value: Any, max_chars: int) -> str | None:
    """`value` stripped and cut to `max_chars` if it's a non-empty string, else None."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:max_chars]


def pick_items(value: Any, max_items: int) -> list[dict]:
    """The dict items of `value` (a list), at most `max_items`; anything else gives []."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][:max_items]


def require_dict(structured: Any) -> dict:
    """`structured` if it's a dict.

    Raises:
        NestedError: It isn't (the session returned no structured output).
    """
    if not isinstance(structured, dict):
        raise NestedError("the session returned no structured output")
    return structured
