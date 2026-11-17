"""Follow the current folder through a shell command's statements, for raw_read_hook.

cd, Set-Location, pushd and subshells move it; popd, Pop-Location and a subshell's
closing `)` move it back. Folders are posix paths relative to where the command
started ("."), so `cd data/raw; cd signal` ends in "data/raw/signal".
"""

import posixpath
import re

# A change of folder (also as a `(cd x && ...)` subshell).
_CHANGE_DIR = re.compile(
    r"^\s*\(?\s*(?:cd|chdir|pushd|Push-Location|Set-Location|sl)\b", re.IGNORECASE
)
_PUSH_DIR = re.compile(r"^\s*(?:pushd|Push-Location)\b", re.IGNORECASE)
_POP_DIR = re.compile(r"^\s*(?:popd|Pop-Location)\b", re.IGNORECASE)


def _next_dir(current_dir: str, statement: str) -> str:
    """The folder a cd statement leads to, relative to the command's start (".")."""
    words = [word.strip("'\")") for word in statement.split()[1:] if not word.startswith("-")]
    target = words[-1].replace("\\", "/") if words else "~"
    return posixpath.normpath(posixpath.join(current_dir, target))


def track_dirs(dirs: list[str], statement: str) -> list[str]:
    """The folder stack after a statement; the last entry is the current folder.

    pushd, Push-Location and each unclosed `(` push; popd, Pop-Location and each
    unmatched `)` pop, so `(cd data/raw/signal && ls); cat a.csv` is back outside.
    Counting parentheses keeps `(x | y).Count` from popping. The bottom entry never
    pops: popd with nothing pushed stays where it is, as in the shell.

    Args:
        dirs: The stack before the statement, starting as ["."].
        statement: One statement (see split_statements).

    Returns:
        The new stack; the argument isn't changed.
    """
    if _POP_DIR.search(statement):
        return dirs[:-1] if len(dirs) > 1 else dirs
    opens = statement.count("(") - statement.count(")")
    pushes = max(opens, 0) + bool(_PUSH_DIR.search(statement))
    dirs = dirs + [dirs[-1]] * pushes
    if _CHANGE_DIR.search(statement):
        dirs = [*dirs[:-1], _next_dir(dirs[-1], statement)]
    return dirs[: max(1, len(dirs) + min(opens, 0))]
