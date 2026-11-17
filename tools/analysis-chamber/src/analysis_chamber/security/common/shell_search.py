"""Read a shell search or listing statement as the folders and globs it covers.

raw_read_hook turns `rg invoice`, `grep -r x .`, `findstr /s x *.txt`,
`Get-ChildItem -Recurse -Filter *.csv` and `find . -name x` into the same path and
glob a Grep tool call would have, so both are judged by one rule. Words are split
on whitespace, so a quoted path with spaces reads as several words (best effort).
"""

import re
from dataclasses import dataclass

# Search verbs, whose first positional word is the pattern unless a flag gave it.
_SEARCH_VERBS = frozenset({"grep", "rg", "findstr", "select-string", "sls"})
# Listing verbs, whose positional words are all paths.
_LIST_VERBS = frozenset({"ls", "dir", "gci", "get-childitem", "find"})
# Always recursive: rg searches and find lists the whole tree below its path.
_ALWAYS_RECURSIVE = frozenset({"rg", "find"})
# Flags that make the others recurse (grep -r / -R / -ri, findstr /s, -Recurse).
_RECURSIVE_FLAGS = frozenset({"--recursive", "--dereference-recursive", "-recurse", "-r", "/s"})
_SHORT_RECURSIVE = re.compile(r"-[a-zA-Z]*[rR][a-zA-Z]*")  # grep and ls flag clusters
_CLUSTER_VERBS = frozenset({"grep", "ls"})
# Flags whose value is a path, a file-name glob, a ripgrep type, or the pattern.
_PATH_FLAGS = frozenset({"-path", "-literalpath"})
_GLOB_FLAGS = frozenset({"-g", "--glob", "--include", "-include", "-filter", "-name", "-iname"})
_TYPE_FLAGS = frozenset({"-t", "--type"})
_PATTERN_FLAGS = frozenset({"-e", "--regexp", "-f", "--file", "-pattern"})
# rg modes that take no pattern, so every positional word is a path (`rg --files code`).
_NO_PATTERN_FLAGS = frozenset({"--files", "--type-list"})
# find's actions: the words after them are a command, not paths (`-exec cat {} ;`).
_FIND_ACTIONS = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
# Other flags that take a value (case-sensitive: grep's -c counts, rg's -C 3 is context).
_VALUE_FLAGS = frozenset({"-m", "-A", "-B", "-C", "--max-count", "--context", "-maxdepth", "-type"})
# Words before the verb that _PRINT_COMMAND also lets through (`& gci`, `(rg x`, xargs).
_LEADING_WORDS = frozenset({"&", "(", "$(", "xargs"})


@dataclass(frozen=True)
class ShellSearch:
    """A shell search or listing.

    Attributes:
        is_recursive: Whether it covers folders below its paths, not just their files.
        paths: Its path words as written (none means the current folder).
        glob: A file-name glob given by a flag (`-g *.py`, `-Filter *.csv`), or "".
        search_type: A ripgrep `-t` type, or "".
    """

    is_recursive: bool
    paths: tuple[str, ...]
    glob: str
    search_type: str


def _words(statement: str) -> list[str]:
    """A statement's words without quotes or parentheses, `--glob=x` split in two."""
    words: list[str] = []
    for word in statement.split():
        word = word.strip("'\"()")
        if word.startswith("--") and "=" in word:
            words.extend(word.split("=", 1))
        elif word:
            words.append(word)
    while words and words[0].lower() in _LEADING_WORDS:
        words.pop(0)
    return words


def _is_recursive_flag(verb: str, flag: str) -> bool:
    """Whether a flag makes the verb recurse."""
    if flag.lower() in _RECURSIVE_FLAGS:
        return True
    return verb in _CLUSTER_VERBS and bool(_SHORT_RECURSIVE.fullmatch(flag))


def parse_shell_search(statement: str) -> ShellSearch | None:
    """A search or listing statement's paths, glob and type.

    Args:
        statement: One statement (see split_statements).

    Returns:
        The search, or None when the statement doesn't start with a search or
        listing verb.
    """
    words = _words(statement)
    verb = words[0].lower() if words else ""
    if verb not in _SEARCH_VERBS | _LIST_VERBS:
        return None
    is_search = verb in _SEARCH_VERBS
    fields = {"glob": "", "search_type": ""}
    flag_paths: list[str] = []
    positionals: list[str] = []
    is_recursive, has_pattern_flag = verb in _ALWAYS_RECURSIVE, False
    rest = iter(words[1:])
    for word in rest:
        flag = word.lower()
        if flag in _FIND_ACTIONS:
            break
        if flag in _PATH_FLAGS:
            flag_paths.append(next(rest, ""))
        elif flag in _GLOB_FLAGS or flag in _TYPE_FLAGS:
            fields["glob" if flag in _GLOB_FLAGS else "search_type"] = next(rest, "")
        elif is_search and (
            flag in _PATTERN_FLAGS or flag in _NO_PATTERN_FLAGS or flag.startswith("/c:")
        ):
            has_pattern_flag = True
            if flag in _PATTERN_FLAGS:
                next(rest, "")
        elif word in _VALUE_FLAGS:
            next(rest, "")
        elif word.startswith("-") or (verb == "findstr" and word.startswith("/")):
            is_recursive = is_recursive or _is_recursive_flag(verb, word)
        else:
            positionals.append(word)
    if is_search and not has_pattern_flag:
        positionals = positionals[1:]  # the first positional word is the pattern
    return ShellSearch(is_recursive, (*flag_paths, *positionals), **fields)
