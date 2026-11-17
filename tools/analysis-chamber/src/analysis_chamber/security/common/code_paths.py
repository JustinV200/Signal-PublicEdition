"""Find file paths inside shell commands and script text, for the path-based hooks.

personal_write_hook and shell_send_hook both need the paths a command names, written
the ways an agent writes them: C:\\x, C:/x, Python's "C:\\\\x", Git Bash /c/x,
and relative ..\\ climbs (resolved against the run folder by the caller).
"""

import re
from pathlib import Path

# Absolute Windows paths (C:\..., C:/...).
_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"|;&<>`,()]*")
# Git Bash paths (/c/...), not the // of a URL or the tail of a relative path.
_GIT_BASH_PATH = re.compile(r"(?<![\w./:])/([A-Za-z])/[^\s'\"|;&<>`,()]*")
# A whole path that is a Git Bash drive path (/c or /c/...), as a file tool may get it.
_GIT_BASH_WHOLE = re.compile(r"^/([A-Za-z])(?=/|$)")
# Relative paths that climb out of the working folder.
_CLIMBING_PATH = re.compile(r"(?<![\w:/\\.])\.\.[\\/][^\s'\"|;&<>`,()]*")
_PATH_PATTERNS = (_WINDOWS_PATH, _GIT_BASH_PATH, _CLIMBING_PATH)


def collapse_escapes(code: str) -> str:
    """Turn Python-escaped doubled backslashes into single ones."""
    return code.replace("\\\\", "\\")


def path_candidates(text: str) -> list[str]:
    """Every path-like string in text; Git Bash /c/x comes back as c:/x."""
    git_bash = [f"{m.group(1)}:/{m.group(0)[3:]}" for m in _GIT_BASH_PATH.finditer(text)]
    return _WINDOWS_PATH.findall(text) + git_bash + _CLIMBING_PATH.findall(text)


def strip_paths(text: str) -> str:
    """Text with its paths blanked, so words inside paths (`a.md`) aren't read as verbs."""
    for pattern in _PATH_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def resolve_against(raw_path: str, base_dir: Path) -> Path:
    """An absolute path for a raw path; relative ones are taken from base_dir.

    A Git Bash drive path (/c/x) is read as c:/x, since the chamber runs on Windows.
    """
    path = Path(_GIT_BASH_WHOLE.sub(r"\1:", raw_path))
    return path if path.is_absolute() else base_dir / path
