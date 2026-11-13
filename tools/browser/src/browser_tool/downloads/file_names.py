"""Safe file names for downloads: the page suggests a name, this decides the real one.

A download's suggested name comes from the server (Content-Disposition) or the
page (an <a download> attribute), so it is untrusted. It must never leave the
downloads folder, never name a Windows device, and never replace a file that is
already there, and must not disguise or arm itself: bidi and zero-width
characters could show "lab<RLO>fdp.exe" as "labexe.pdf", and Explorer acts on
some files (.url, .lnk, .scf...) just by showing the folder.
"""

import re
from pathlib import Path

from browser_tool.redaction import replace_unsafe_chars

# Path separators and Windows' forbidden characters (":" also opens an NTFS
# alternate data stream). Control and format characters are replaced too
# (redaction.replace_unsafe_chars).
UNSAFE_CHARACTERS = re.compile(r'[<>:"/\\|?*]')
# Shell-handled types Explorer can act on without a double-click (fetch an icon
# from a remote share, leaking the NTLM hash) or that run on open.
SHELL_SUFFIXES = (".url", ".scf", ".lnk", ".library-ms", ".searchconnector-ms")
DISARMED_SUFFIX = ".download"
REPLACEMENT = "_"
FALLBACK_NAME = "download"
MAX_NAME_CHARS = 120
# Longer "extensions" are just part of the name, so truncation may cut them.
MAX_SUFFIX_CHARS = 16
MAX_CLASHES = 1000
# Windows device names: "CON", "con.txt" and "COM1.tar.gz" all open the device.
_DEVICES = ("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$")
_NUMBERED = ("COM", "LPT")
_DIGITS = (*"0123456789", "¹", "²", "³")
RESERVED_NAMES = frozenset(_DEVICES) | {prefix + digit for prefix in _NUMBERED for digit in _DIGITS}


def safe_file_name(suggested: str) -> str:
    """Turn an untrusted suggested name into one plain file name for the downloads folder.

    Args:
        suggested: The name the server or page suggested.

    Returns:
        A name with no path separators or forbidden characters, no leading or
        trailing dots or spaces (so no "." or ".."), no control or format
        characters, not a Windows device name, at most MAX_NAME_CHARS long
        (plus DISARMED_SUFFIX on a shell-handled type). FALLBACK_NAME when
        nothing is left.
    """
    name = replace_unsafe_chars(UNSAFE_CHARACTERS.sub(REPLACEMENT, suggested), REPLACEMENT)
    name = _truncate(name.strip(" ."))
    if not name:
        return FALLBACK_NAME
    # Windows ignores trailing spaces before the first dot: "CON .txt" is CON too.
    if name.split(".", 1)[0].rstrip(" ").upper() in RESERVED_NAMES:
        name = REPLACEMENT + name
    if name.lower().endswith(SHELL_SUFFIXES):
        name += DISARMED_SUFFIX
    return name


def reserve_path(folder: Path, name: str) -> Path:
    """Create an empty file for `name` in `folder`, adding " (1)", " (2)"... on a clash.

    The file is created exclusively, so two downloads with one name can't both
    claim it and an existing file is never overwritten.

    Args:
        folder: The downloads folder (created if missing).
        name: A name from safe_file_name.

    Returns:
        The new empty file's path, always directly inside `folder`.

    Raises:
        ValueError: If the name would land outside `folder` (safe_file_name prevents it).
        OSError: If the folder can't be written or MAX_CLASHES names are all taken.
    """
    folder.mkdir(parents=True, exist_ok=True)
    stem, suffix = _split_suffix(name)
    for counter in range(MAX_CLASHES):
        candidate = folder / (name if counter == 0 else f"{stem} ({counter}){suffix}")
        if candidate.resolve().parent != folder.resolve():
            raise ValueError("download name leaves the downloads folder")
        try:
            candidate.open("xb").close()
        except FileExistsError:
            continue
        return candidate
    raise OSError(f"{MAX_CLASHES} downloads already use this name")


def _split_suffix(name: str) -> tuple[str, str]:
    """("notes", ".ipynb") for "notes.ipynb"; no suffix for long or dot-free endings."""
    suffix = Path(name).suffix
    if len(suffix) > MAX_SUFFIX_CHARS:
        return name, ""
    return name[: len(name) - len(suffix)], suffix


def _truncate(name: str) -> str:
    """Cut an over-long name, keeping its suffix, and re-strip what the cut exposed."""
    if len(name) <= MAX_NAME_CHARS:
        return name
    stem, suffix = _split_suffix(name)
    return (stem[: MAX_NAME_CHARS - len(suffix)].rstrip(" .") + suffix).strip(" .")
