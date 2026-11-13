"""Check and read one local file for upload_file or read_download. Pure: no browser.

A file is read only when all of these hold:
- before any filesystem call, the path is a plain drive-letter path (no UNC
  share, which would open an SMB connection and leak an NTLM handshake, no
  \\?\\ or \\.\\ prefix, no device name such as CON or nul.txt, no ":" past
  the drive) whose normalized form is inside one of the roots ([uploads]
  roots, or the downloads folder);
- no part of it, walked from the drive root down with lstat before anything
  follows a link, is a symlink, junction or other reparse point (so a link to
  a network share is never followed);
- it resolves to itself: no 8.3 short name or other redirect on the way;
- it is inside one of the roots (after resolving them);
- no part of it is the vault's folder (signal-vault, in %LOCALAPPDATA%), a
  browser profile (.profile*), the saved-cookies folder (.state), an .env
  file (.env, .env.local, prod.env), or a key file (.pem, .key, .pfx,
  id_rsa...), in any letter case;
- it is a regular file with one hard link (a hard link could be the vault's
  file under another name), at most max_bytes long.
The file is opened once, and the open file is checked to be the same file the
path checks saw (device and inode), so it can't be swapped in between; its
bytes are what the caller uses, never the path. After the open the path is
resolved again and must still be the same, which narrows (but can't close) a
swap of a folder for a junction between the checks and the open. Refusals
never echo file content.
"""

import mimetypes
import os
import re
import stat
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from browser_tool.actions.errors import ActionError

VAULT_DIR_NAME = "signal-vault"
# tools/browser/.state, where the desktop browser's cookies are saved (cookie_store).
STATE_DIR_NAME = ".state"
KEY_SUFFIXES = frozenset(
    {".pem", ".key", ".pfx", ".p12", ".kdbx", ".ppk", ".jks", ".keystore", ".gpg", ".asc"}
)
KEY_NAME_PREFIXES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
DEFAULT_MIME = "application/octet-stream"
# On Windows, os.open needs O_BINARY to read bytes unchanged (0 elsewhere).
OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0)
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
# "C:\..." or "C:/...": a drive letter, one separator, then not a second one.
DRIVE_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?![\\/])")
# Windows device names, which open a device whatever the folder or extension.
DEVICE_NAME_RE = re.compile(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", re.IGNORECASE)

NOT_ABSOLUTE = (
    "refused: give the file's full path on a drive (e.g. C:\\src\\Signal\\life\\...); "
    "network shares and device paths are never opened"
)
DEVICE_NAME = "refused: that names a Windows device or a data stream, not a file"
NOT_FOUND = "refused: no such file"
NOT_DIRECT = "refused: the path goes through a link, junction or short name; use the real path"
OUTSIDE_ROOTS = "refused: the file must come from {roots}"
FORBIDDEN = (
    "refused: that file is never read (vault, browser profile, saved cookies, .env or key file)"
)
NOT_REGULAR = "refused: not a regular file with a single name"
TOO_BIG = "refused: the file is over the {max_mb:g} MB limit"
CHANGED = "refused: the file changed while it was being checked; try again"


class CheckedFile(NamedTuple):
    """A checked file, read into memory.

    Attributes:
        name: Its file name (what the page sees).
        data: Its bytes.
        mime: Its MIME type, guessed from the name.
    """

    name: str
    data: bytes
    mime: str


def read_checked_file(path: str, roots: Sequence[Path], max_bytes: int) -> CheckedFile:
    """Check `path` against the rules (module docstring) and read it once.

    Args:
        path: The path the model gave.
        roots: The folders the file may come from (absolute).
        max_bytes: The size cap.

    Raises:
        ActionError: With the reason the file is refused.
    """
    given = _plain_drive_path(path)
    # Lexical first, so nothing outside the roots is ever touched on disk.
    _ensure_inside(Path(os.path.abspath(given)), [Path(os.path.abspath(root)) for root in roots])
    resolved = _resolve_directly(given)
    _ensure_inside(resolved, [root.resolve() for root in roots])
    if _is_forbidden(resolved):
        raise ActionError(FORBIDDEN)
    checked = os.lstat(resolved)
    if not stat.S_ISREG(checked.st_mode):
        raise ActionError(NOT_REGULAR)
    data = _read_same_file(resolved, checked, max_bytes)
    mime = mimetypes.guess_type(resolved.name)[0] or DEFAULT_MIME
    return CheckedFile(resolved.name, data, mime)


def _plain_drive_path(path: str) -> Path:
    """`path` as a Path, checked without touching the filesystem.

    Raises:
        ActionError: NOT_ABSOLUTE for anything but a plain drive-letter path,
            DEVICE_NAME for a device name or a ":" past the drive.
    """
    if not DRIVE_PATH_RE.match(path):
        raise ActionError(NOT_ABSOLUTE)
    given = Path(path)
    for part in given.parts[1:]:
        # Windows reads the name before the first dot, trailing spaces dropped:
        # "nul.txt" and "CON .log" are devices too.
        if ":" in part or DEVICE_NAME_RE.fullmatch(part.split(".")[0].rstrip(" ")):
            raise ActionError(DEVICE_NAME)
    # abspath is lexical (GetFullPathNameW); it must still give a drive path.
    if not DRIVE_PATH_RE.match(os.path.abspath(given)):
        raise ActionError(NOT_ABSOLUTE)
    return given


def _ensure_inside(path: Path, roots: Sequence[Path]) -> None:
    """Refuse `path` unless it is inside one of `roots` (compared folded).

    Raises:
        ActionError: OUTSIDE_ROOTS.
    """
    if not any(_folded(path).is_relative_to(_folded(root)) for root in roots):
        shown = ", ".join(str(root) for root in roots) or "nowhere (no folders configured)"
        raise ActionError(OUTSIDE_ROOTS.format(roots=shown))


def _folded(path: Path) -> Path:
    """`path` for comparing: case-insensitive with backslashes on Windows (as-is elsewhere)."""
    return Path(os.path.normcase(path))


def _resolve_directly(given: Path) -> Path:
    """The resolved path (in its real letter case), refusing a redirected one.

    A link, junction or 8.3 short name anywhere on the way redirects it. Links
    are looked for first (_ensure_no_links), since resolve follows them.

    Raises:
        ActionError: NOT_FOUND, or NOT_DIRECT.
    """
    absolute = Path(os.path.abspath(given))
    _ensure_no_links(absolute)
    try:
        resolved = given.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ActionError(NOT_FOUND) from None
    if _folded(resolved) != _folded(absolute) or ":" in resolved.name:
        raise ActionError(NOT_DIRECT)  # ":" also refuses an NTFS alternate data stream
    return resolved


def _ensure_no_links(absolute: Path) -> None:
    """lstat each part of `absolute` from the drive root down; refuse a link or reparse point.

    Top-down, so the first link stops the walk before any later lstat goes
    through it (lstat follows links in the folders above the last part).

    Raises:
        ActionError: NOT_FOUND, or NOT_DIRECT.
    """
    for part in [*reversed(absolute.parents), absolute]:
        try:
            info = os.lstat(part)
        except OSError:
            raise ActionError(NOT_FOUND) from None
        is_reparse = getattr(info, "st_file_attributes", 0) & REPARSE_POINT
        if stat.S_ISLNK(info.st_mode) or is_reparse:
            raise ActionError(NOT_DIRECT)


def _is_forbidden(resolved: Path) -> bool:
    """True for the vault, a browser profile, saved cookies, an .env or key file (any case)."""
    for part in (name.lower() for name in resolved.parts):
        if part in (VAULT_DIR_NAME, STATE_DIR_NAME) or part.startswith(".profile"):
            return True
        if part.endswith(".env") or part.startswith(".env."):
            return True
    name = resolved.name.lower()
    return resolved.suffix.lower() in KEY_SUFFIXES or name.startswith(KEY_NAME_PREFIXES)


def _read_same_file(resolved: Path, checked: os.stat_result, max_bytes: int) -> bytes:
    """Open `resolved` once, make sure it is the file `checked` describes, and read it.

    Raises:
        ActionError: NOT_REGULAR, TOO_BIG or CHANGED.
    """
    try:
        descriptor = os.open(resolved, OPEN_FLAGS)
    except OSError:
        raise ActionError(NOT_FOUND) from None
    with os.fdopen(descriptor, "rb") as opened:
        info = os.fstat(opened.fileno())
        if (info.st_dev, info.st_ino) != (checked.st_dev, checked.st_ino):
            raise ActionError(CHANGED)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ActionError(NOT_REGULAR)
        too_big = TOO_BIG.format(max_mb=max_bytes / (1024 * 1024))
        if info.st_size > max_bytes:
            raise ActionError(too_big)
        data = opened.read(max_bytes + 1)
    # Narrows a folder swapped for a junction between the checks and the open.
    try:
        is_same_path = _folded(resolved.resolve(strict=True)) == _folded(resolved)
    except (OSError, RuntimeError):
        is_same_path = False
    if not is_same_path:
        raise ActionError(CHANGED)
    if len(data) > max_bytes:  # it grew after the size check
        raise ActionError(too_big)
    return data
