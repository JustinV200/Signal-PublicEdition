"""Placeholder values the shipped examples use, which the user must replace.

Reserved example domains, YOUR_ / YOUR- names, <angle-bracket> slots and TODO(...) markers.
Only values are checked (format modules skip comments and prose), so an example host
in a comment never counts. Markdown list lines can be prose too (the jobhunt runbook's
`- Result: append ... <gmail message id> ...`), so there a slot counts only when the
value is nothing but slots.
"""

import re
from pathlib import Path
from typing import Any

from signal_setup.settings.formats import for_path, md_lines

PATTERN = re.compile(r"example\.(?:edu|com|org)|YOUR[_-]|<[^<>\n]+>|TODO\(")
# The markers that are never prose: they count anywhere in a value.
_MARKERS = re.compile(r"example\.(?:edu|com|org)|YOUR[_-]|TODO\(")
# A value that is only <slots> (with separators between them): a blank to fill in.
# shortcut: a slot inside other text in a Markdown line ("<your city>, NY") isn't flagged;
# give such an example line a TODO( marker if the owner must fill it in.
_SLOTS_ONLY = re.compile(r"(?:<[^<>\n]+>[\s,;/]*)+")


def is_prose_file(path: str | Path) -> bool:
    """True for a file read as `- Label: value` lines among prose (md_lines).

    Not AGENTS.md: it's Markdown too, but its settings sit in marked comments (md_marked).
    """
    try:
        return for_path(path) is md_lines
    except ValueError:  # a format setup can't edit has no settings, so no prose either
        return False


def is_placeholder(value: Any, in_prose: bool = False) -> bool:
    """True when a value, or any item of a list value, is still a placeholder.

    Args:
        value: A config value (str, list, number, bool).
        in_prose: The value is a Markdown list line's text, where a slot inside a
            sentence is the run's own template syntax ("from <old date>"), not a blank.
    """
    if isinstance(value, list):
        return any(is_placeholder(item, in_prose) for item in value)
    if not isinstance(value, str):
        return False
    if in_prose:
        return bool(_MARKERS.search(value) or _SLOTS_ONLY.fullmatch(value.strip()))
    return PATTERN.search(value) is not None
