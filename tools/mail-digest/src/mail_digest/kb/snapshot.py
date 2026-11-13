"""Snapshots life/ before a run, so the KB guard (guard.py) can diff against it after.

Links, junctions and other reparse points are skipped, files and folders alike. One
the owner made could point outside life/ (a big archive, a private folder), and the
job's targets never go through one (targets.py skips those).

Only the editable files (and paths under them) are kept as bytes, since the guard
diffs and restores just those. Everything else is kept as a SHA-256 digest, which is
enough to tell that it changed, so life/ isn't held in memory twice.
"""

import hashlib
import logging
import os
import stat
from pathlib import Path

from mail_digest.kb.paths import is_covered

log = logging.getLogger(__name__)


def snapshot(life_dir: Path, editable: tuple[str, ...]) -> dict[str, bytes]:
    """Every plain file under life_dir: POSIX path relative to it -> bytes or digest.

    editable: the run's editable paths. Those files, and any under them, map to their
    exact bytes; every other file maps to its SHA-256 digest. Take the before and
    after snapshots with the same editable paths, so a key is stored the same way in
    both. A file or folder that can't be read is skipped and logged, never raised.
    """
    files = {}
    for folder, subfolders, names in os.walk(life_dir, onerror=_log_walk_error):
        root = Path(folder)
        # Pruning in place keeps os.walk out of linked folders.
        subfolders[:] = [name for name in subfolders if _plain_mode(root / name) is not None]
        for name in names:
            path = root / name
            mode = _plain_mode(path)
            if mode is None or not stat.S_ISREG(mode):
                continue
            relative = path.relative_to(life_dir).as_posix()
            content = _read(path, keep_bytes=is_covered(relative, editable))
            if content is not None:
                files[relative] = content
    return dict(sorted(files.items()))


def _plain_mode(path: Path) -> int | None:
    """path's st_mode, or None for a link, junction or other reparse point (never followed).

    os.walk treats a junction as a plain folder, so the attribute is checked too. A
    path that can't be stat'ed (gone, or no access) is logged and None.
    """
    try:
        info = path.lstat()
    except OSError as error:
        log.warning("snapshot skipped %s: %s", path, error)
        return None
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return None
    return info.st_mode


def _read(path: Path, keep_bytes: bool) -> bytes | None:
    """The file's bytes (keep_bytes) or SHA-256 digest; None if it can't be read (logged)."""
    try:
        if keep_bytes:
            return path.read_bytes()
        with path.open("rb") as file:
            return hashlib.file_digest(file, "sha256").digest()
    except OSError as error:
        log.warning("snapshot skipped %s: %s", path, error)
        return None


def _log_walk_error(error: OSError) -> None:
    """os.walk's onerror: a folder it can't list is skipped, and logged here."""
    log.warning("snapshot skipped %s: %s", error.filename, error)
