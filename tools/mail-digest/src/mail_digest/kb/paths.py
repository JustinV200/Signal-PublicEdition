"""How the KB snapshot and guard compare life/ paths: ASCII case only.

NTFS and Claude Code's Edit rules treat INBOX.MD and inbox.md as one name, but not
the Kelvin sign and K, long s and s, ß and ss, or a ligature and its letters, which
str.casefold() would merge. Merging those would make a look-alike file someone else
made beside a target count as the target. KB targets are ASCII (targets.SAFE_PATH),
so lowercasing A-Z alone is exact for them.
"""

import string
from collections.abc import Iterable

ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def fold_case(path: str) -> str:
    """path with A-Z lowercased and every other character kept as it is."""
    return path.translate(ASCII_LOWER)


def is_covered(path: str, editable: Iterable[str]) -> bool:
    """True if path is one of the editable paths or under one, ignoring ASCII case.

    "Under" counts because the Edit rules match gitignore-style: Edit(/inbox.md)
    also allows inbox.md/x.md when inbox.md isn't a file.
    """
    key = fold_case(path)
    return any(key == target or key.startswith(target + "/") for target in map(fold_case, editable))
