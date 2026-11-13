"""Checks for `MusicController` method arguments, shared by every backend and the CLI.

These run at the package boundary (calls from the CLI, MCP tools and the
voice loop), so a bad value fails with a clear ValueError before any request.
"""

import typing

from audiohub.music.controller import SEARCH_KINDS, SearchKind

MIN_VOLUME_PERCENT = 0
MAX_VOLUME_PERCENT = 100


def check_volume_percent(percent: int) -> int:
    """Return `percent` if it's a whole number from 0 to 100.

    Raises:
        ValueError: If it isn't an int (bools excluded) or is out of range.
    """
    if isinstance(percent, bool) or not isinstance(percent, int):
        raise ValueError(f"volume must be a whole number, got {percent!r}")
    if not MIN_VOLUME_PERCENT <= percent <= MAX_VOLUME_PERCENT:
        raise ValueError(
            f"volume must be between {MIN_VOLUME_PERCENT} and {MAX_VOLUME_PERCENT}, got {percent}"
        )
    return percent


def check_query(query: str) -> str:
    """Return the search query with surrounding whitespace removed.

    Raises:
        ValueError: If it's blank.
    """
    stripped = query.strip()
    if not stripped:
        raise ValueError("search query must not be empty")
    return stripped


def check_search_kind(kind: str) -> SearchKind:
    """Return `kind` if it's one of SEARCH_KINDS.

    Raises:
        ValueError: If it isn't.
    """
    if kind not in SEARCH_KINDS:
        raise ValueError(f"search kind must be one of {', '.join(SEARCH_KINDS)}, got {kind!r}")
    return typing.cast(SearchKind, kind)
