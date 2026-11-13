"""Header lookup for Gmail message parts: the first value of each name, or every value of one."""

from collections.abc import Iterator
from typing import Any


def header_map(part: dict[str, Any]) -> dict[str, str]:
    """Collect a payload part's headers, keeping the first value of each name.

    Args:
        part: A Gmail MessagePart (message["payload"] or one of its parts).

    Returns:
        {lower-cased header name: value}. Malformed entries are skipped.
    """
    headers: dict[str, str] = {}
    for name, value in _pairs(part):
        headers.setdefault(name, value)
    return headers


def header_values(part: dict[str, Any], name: str) -> list[str]:
    """Every value of one header, in order. A message can repeat a header such as To.

    Args:
        part: A Gmail MessagePart.
        name: The header name (any case).

    Returns:
        The values; [] when the header is absent.
    """
    wanted = name.lower()
    return [value for header, value in _pairs(part) if header == wanted]


def _pairs(part: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """(lower-cased name, value) for each well-formed header entry."""
    for item in part.get("headers") or []:
        if isinstance(item, dict) and item.get("name"):
            yield str(item["name"]).lower(), str(item.get("value", ""))
