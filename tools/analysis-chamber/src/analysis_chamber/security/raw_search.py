"""Whether a Grep or Glob would search into <run>/data/raw/signal/, for raw_read_hook.

A search rooted at or above that folder reaches it unless its glob can't: Grep with no
`glob` or `type` from the run folder (or `path: data`) would hand raw mail text to the
lead in content mode, and Glob `**/*` lists the raw files. Raw Signal files are always
`<nnn>-<tool>.txt` (agents.fetch.signal_swap), so a glob whose last segment can only
match other extensions (`**/*.csv`, `*.{py,ipynb}`, `data/**/*.parquet`) and a Grep
`type` other than `txt` keep out of it. Anything that could match a `.txt` file there
(`*`, `*.txt`, `*.t?t`, `!*.csv`, `**`) counts.
"""

import fnmatch
import re
from pathlib import Path, PurePath
from typing import Any

from analysis_chamber.guard import is_under
from analysis_chamber.security.common import resolve_against

# raw/signal as a folder: followed by a separator or the end, not `signal.csv`.
RAW_SIGNAL_TEXT = re.compile(r"raw[\\/]+signal(?![\w.-])", re.IGNORECASE)

_GLOB_STAR = "**"
# The raw files' extension (signal_swap saves `<nnn>-<tool>.txt`).
_RAW_EXTENSION = "txt"
# ripgrep `--type` names whose globs match `*.txt` (`all` matches every typed file).
_RAW_TYPES = frozenset({_RAW_EXTENSION, "all"})
# A brace group in a glob (`{py,ipynb}`), expanded into alternatives.
_BRACE_GROUP = re.compile(r"\{([^{}]*)\}")
# A plain literal extension at the end of a glob: `.csv`, not `.t?t` or `.*`.
_LITERAL_EXTENSION = re.compile(r"\.(\w+)$")


def _alternatives(segment: str) -> list[str]:
    """A glob segment's alternatives: braces expanded, and split on `,` (`*.py,*.txt`)."""
    match = _BRACE_GROUP.search(segment)
    if match:
        head, tail = segment[: match.start()], segment[match.end() :]
        return [
            alt
            for option in match.group(1).split(",")
            for alt in _alternatives(head + option + tail)
        ]
    return segment.split(",")


def _may_match_raw_file(segment: str) -> bool:
    """Whether a glob's last segment could match a raw `.txt` file name.

    Safe only when every alternative ends in a literal extension other than txt; a
    negation (`!*.csv`) matches everything else, so it counts.
    """
    for alternative in _alternatives(segment):
        match = _LITERAL_EXTENSION.search(alternative)
        if alternative.startswith("!") or not match or match.group(1).lower() == _RAW_EXTENSION:
            return True
    return False


def _glob_reaches(pattern_parts: list[str], dir_parts: list[str]) -> bool:
    """Whether a glob (split on /) can match files inside dir_parts (split on /).

    `**` matches any number of folders, including raw/signal itself.
    """
    if not dir_parts:
        return bool(pattern_parts)  # parts left over match something inside the folder
    if not pattern_parts:
        return False
    head, rest = pattern_parts[0], pattern_parts[1:]
    if head == _GLOB_STAR:
        # A trailing `**` matches every file below; otherwise try each depth for it.
        return not rest or any(
            _glob_reaches(rest, dir_parts[skip:]) for skip in range(len(dir_parts) + 1)
        )
    return fnmatch.fnmatch(dir_parts[0].lower(), head.lower()) and _glob_reaches(
        rest, dir_parts[1:]
    )


def _glob_reaches_raw(root: Path, pattern: str, raw_dir: Path) -> bool:
    """Whether a glob rooted at root names raw_dir or can match its raw files."""
    if RAW_SIGNAL_TEXT.search(pattern):
        return True
    pure = PurePath(pattern)
    if pure.is_absolute():  # the pattern carries its own root
        root, pattern = Path(pure.anchor), "/".join(pure.parts[1:])
    if not is_under(raw_dir, root):
        return False
    dir_parts = list(raw_dir.resolve().relative_to(root.resolve()).parts)
    parts = pattern.replace("\\", "/").split("/")
    return _glob_reaches(parts, dir_parts) and _may_match_raw_file(parts[-1])


def _grep_reaches_raw(tool_input: dict[str, Any], root: Path, raw_dir: Path) -> bool:
    """Whether a Grep from root searches raw_dir, judged by its glob, else its type."""
    if not is_under(raw_dir, root):
        return False
    glob = str(tool_input.get("glob") or "")
    if glob:
        # ripgrep's -g overrides -t, so the glob decides; one without a slash matches
        # file names at any depth.
        return _glob_reaches_raw(root, glob if "/" in glob else f"**/{glob}", raw_dir)
    search_type = str(tool_input.get("type") or "").lower()
    return not search_type or search_type in _RAW_TYPES


def search_reaches_raw(
    tool_name: str, tool_input: dict[str, Any], run_dir: Path, raw_dir: Path
) -> bool:
    """Whether a Grep or Glob call would search or list files in raw_dir.

    Args:
        tool_name: "Grep" or "Glob" (anything else returns False).
        tool_input: The tool's input; `path` defaults to the run folder.
        run_dir: Where a relative `path` starts.
        raw_dir: <run>/data/raw/signal.

    Returns:
        True when the search root is at or above raw_dir and neither the glob nor
        Grep's `type` keeps it to folders outside raw_dir or to non-`.txt` files.
    """
    root = resolve_against(str(tool_input.get("path") or "."), run_dir)
    if tool_name == "Grep":
        return _grep_reaches_raw(tool_input, root, raw_dir)
    if tool_name == "Glob":
        return _glob_reaches_raw(root, str(tool_input.get("pattern") or ""), raw_dir)
    return False
