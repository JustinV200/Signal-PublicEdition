"""Placeholder values the shipped examples use, which the user must replace.

Reserved example domains, YOUR_ / YOUR- names, <angle-bracket> slots and TODO(...) markers.
Only values are checked (format modules skip comments and prose), so an example host
in a comment never counts.
"""

import re
from typing import Any

PATTERN = re.compile(r"example\.(?:edu|com|org)|YOUR[_-]|<[^<>\n]+>|TODO\(")


def is_placeholder(value: Any) -> bool:
    """True when a value, or any item of a list value, is still a placeholder."""
    if isinstance(value, list):
        return any(is_placeholder(item) for item in value)
    return isinstance(value, str) and PATTERN.search(value) is not None
