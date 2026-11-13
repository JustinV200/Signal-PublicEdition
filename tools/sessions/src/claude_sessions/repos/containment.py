r"""require_inside_roots: the one check that a session folder is a local folder under a repo root.

A managed session loads the folder's project and local settings, and with them
its hooks, which run without any dialog. So a session may only start, resume
or be adopted in a folder that, after following every link and junction, is
inside one of the configured roots (C:\src by default).

Network (UNC) and device (\\?\, \\.\) paths are refused before the disk is
touched: even resolving a UNC path opens an SMB connection, which can leak
the user's NTLM hash to that host. The drive is parsed with PureWindowsPath,
which normalises the slashes, so mixed forms such as /\host\share and
\/host/share are caught too.
"""

import os
from collections.abc import Iterable
from pathlib import Path, PureWindowsPath

# How a UNC share or device-namespace drive starts once the slashes are normalised.
_UNC_OR_DEVICE_DRIVE_PREFIX = "\\\\"
# Characters that only appear in device-namespace drives (\\?\..., \\.\...).
_DEVICE_DRIVE_MARKERS = ("?", ".")


class RepoNotFoundError(LookupError):
    """No folder or repo name matches what was asked for, or several do."""


class RepoOutsideRootsError(RepoNotFoundError):
    """The folder is a network/device path, or resolves outside every repo root."""


def require_inside_roots(path_text: str | Path, roots: Iterable[Path]) -> Path:
    """Resolve a folder path and check that it lies inside a repo root.

    Args:
        path_text: An absolute folder path, as given by a caller or a transcript.
        roots: The configured repo roots.

    Returns:
        The fully resolved folder.

    Raises:
        RepoOutsideRootsError: A UNC or device path, a relative path, or a
            folder whose resolved location is outside every root.
        RepoNotFoundError: The path doesn't exist or isn't a folder.
    """
    text = str(path_text).strip()
    # Only string checks until the path is known to be local: no filesystem call
    # may ever see a UNC path.
    if is_network_or_device(text):
        raise RepoOutsideRootsError(f"{text} is a network or device path; use a local folder.")
    path = Path(text)
    if not path.is_absolute():
        raise RepoOutsideRootsError(f"{text} isn't an absolute folder path.")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RepoNotFoundError(f"{text} isn't an existing folder.") from error
    if not resolved.is_dir():
        raise RepoNotFoundError(f"{text} isn't a folder.")
    resolved_roots = _resolved_roots(roots)
    # A mapped network drive can resolve to a UNC path; that isn't local either.
    is_inside = any(is_within(resolved, root) for root in resolved_roots)
    if is_network_or_device(str(resolved)) or not is_inside:
        allowed = ", ".join(str(root) for root in resolved_roots) or "(no existing roots)"
        raise RepoOutsideRootsError(f"{resolved} is outside the repo roots ({allowed}).")
    return resolved


def is_network_or_device(path_text: str) -> bool:
    r"""Whether a path names a UNC share or a device namespace, judged from the text alone.

    Args:
        path_text: Any path string, in either slash style or a mix.

    Returns:
        True for \\host\share, //host/share, /\host\share, \/host/share, \\?\...,
        \\.\... and the like; False for ordinary drive paths such as C:\src.
    """
    drive = PureWindowsPath(path_text).drive
    if drive.startswith(_UNC_OR_DEVICE_DRIVE_PREFIX):
        return True
    return any(marker in drive for marker in _DEVICE_DRIVE_MARKERS)


def is_within(folder: Path, root: Path) -> bool:
    """Whether folder is root or below it, ignoring case on Windows. Both must be resolved.

    Args:
        folder: The folder to test.
        root: The root it should be under.

    Returns:
        True when folder equals root or is inside it.
    """
    folder_key = os.path.normcase(str(folder))
    root_key = os.path.normcase(str(root))
    return folder_key == root_key or folder_key.startswith(root_key.rstrip(os.sep) + os.sep)


def _resolved_roots(roots: Iterable[Path]) -> list[Path]:
    """The local roots that exist, fully resolved (a root behind a junction counts where it points).

    A network or device root is skipped without being resolved, for the same
    SMB reason as above.
    """
    resolved: list[Path] = []
    for root in roots:
        if is_network_or_device(str(root)):
            continue
        try:
            resolved.append(Path(root).resolve(strict=True))
        except OSError:
            continue
    return resolved
