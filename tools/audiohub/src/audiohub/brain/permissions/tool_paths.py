"""Finds the paths a tool call targets and resolves them to the real files the OS would open.

secret_paths.py uses this to refuse a Read, Glob or Grep of a secret under any
spelling. Paths are resolved on the real filesystem (os.path.realpath), so
symlinks, junctions and 8.3 short names ("CLAUDE~1") are followed the way
Windows follows them. String normalizing alone misses those aliases
(tools/whiteboard's agent/permissions.py records the same lesson). Aliases
realpath can't see through make a path untrusted, and every check fails
closed on it.
"""

import os
from collections.abc import Mapping
from pathlib import Path, PurePath

# Input fields that hold a path for the built-in file tools
# (Read, Edit, Write, MultiEdit, NotebookEdit, Glob, Grep).
PATH_FIELDS = ("file_path", "notebook_path", "path")

# Glob's "pattern" is itself a path and may be absolute ("C:/Users/**/*.pem").
# Grep's "pattern" is a regex, so only Glob's counts.
TOOLS_WITH_PATH_PATTERN = frozenset({"Glob"})

# Windows drops a trailing "." or " " from a path part, so "x." opens "x". Only
# these two parts may legitimately end in a dot.
DOT_PARTS = frozenset({os.curdir, os.pardir})
ALIAS_PART_ENDINGS = (".", " ")

# UNC and device paths (\\server\share, \\?\C:\, \\.\C:). Resolving one would
# make Windows contact the named machine, so they are rejected unresolved.
UNC_PREFIXES = ("\\\\", "//")


def text_field(tool_input: Mapping[str, object], key: str) -> str:
    """Read a string field from a tool's input.

    Args:
        tool_input: The tool's input mapping, as sent by Claude.
        key: The field to read.

    Returns:
        The value with surrounding whitespace stripped, or "" when it is missing
        or not a string.
    """
    value = tool_input.get(key)
    return value.strip() if isinstance(value, str) else ""


def target_paths(tool_name: str, tool_input: Mapping[str, object]) -> list[str]:
    """List the non-empty path-like fields of a tool call.

    Args:
        tool_name: The tool's name, which decides whether "pattern" is a path.
        tool_input: The tool's input as Claude sent it.

    Returns:
        The raw path strings, in field order.
    """
    fields = PATH_FIELDS + (("pattern",) if tool_name in TOOLS_WITH_PATH_PATTERN else ())
    return [path for path in (text_field(tool_input, field) for field in fields) if path]


def resolve_path(path: str, root: Path) -> str | None:
    """Resolve a path to the real file the OS would open.

    "~" is expanded, a relative path is joined to root, then symlinks, junctions
    and 8.3 short names are followed. Glob wildcards are kept as written.

    Args:
        path: An absolute or relative path, possibly with glob wildcards.
        root: The project folder; relative paths are taken from here.

    Returns:
        The real absolute path, or None when it can't be trusted: a NUL, an
        alternate data stream ("a.txt:evil" or "::$DATA"), a part ending in "."
        or " ", a UNC or device path, or a path the OS refuses to resolve.
    """
    if "\0" in path:
        return None
    candidate = Path(os.path.expanduser(path))
    # Joining also handles "\\etc" on Windows: it keeps root's drive and lands outside root.
    absolute = str(candidate if candidate.is_absolute() else root / candidate)
    drive, rest = os.path.splitdrive(absolute)
    if drive.startswith(UNC_PREFIXES) or ":" in rest or _has_alias_part(rest):
        return None
    try:
        return os.path.realpath(absolute)
    except (OSError, ValueError):
        return None


def _has_alias_part(path: str) -> bool:
    """Whether any part of a (drive-less) path ends in a dot or space Windows would drop."""
    return any(
        part.endswith(ALIAS_PART_ENDINGS) for part in path.split(os.sep) if part not in DOT_PARTS
    )


def relative_parts(path: str, root: Path) -> tuple[str, ...] | None:
    """Resolve a path and list its parts below the resolved root, case-folded.

    Args:
        path: An absolute or relative path, possibly with glob wildcards.
        root: The project folder. It is resolved too, so a root reached through a
            junction or short name still matches.

    Returns:
        () for root itself, parts starting with ".." when the path is outside
        root, or None when the path is untrusted (see resolve_path) or on
        another drive.
    """
    resolved = resolve_path(path, root)
    resolved_root = resolve_path(str(root), root)
    if resolved is None or resolved_root is None:
        return None
    try:
        # relpath compares case-insensitively on Windows.
        relative = os.path.relpath(resolved, resolved_root)
    except (OSError, ValueError):
        # Different drives (C: vs D:) have no relative path.
        return None
    return tuple(part.casefold() for part in PurePath(relative).parts)
