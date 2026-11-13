"""Image paths for `image` items and GET /files: the boundary between web requests and the disk.

GET /files can be triggered by any web page (a cross-site <img> sends no Origin),
so a path is checked in two stages:
1. `check_image_path` is pure string validation, with no filesystem call at all.
   That matters because merely resolving `\\\\host\\share\\x.png` or `//host/x.png`
   on Windows opens an SMB/WebDAV connection and leaks the owner's NTLM hash.
   Only forward-slash, repo-relative paths into IMAGE_DIRS pass.
2. `resolve_image_path` then resolves links and junctions and checks the real
   file is still inside an allowed folder.
"""

from pathlib import Path, PurePosixPath

from whiteboard.config import REPO_ROOT, STATE_DIR
from whiteboard.display.scene.model import SceneError

IMAGE_SUFFIXES: tuple[str, ...] = (".png", ".jpg", ".jpeg")
# Repo-relative folders images may come from: .state/ holds the camera snapshots.
IMAGE_DIRS: tuple[str, ...] = (STATE_DIR.relative_to(REPO_ROOT).as_posix(),)
MAX_IMAGE_PATH_CHARS = 260
# Windows opens these as devices whatever folder or extension they're given.
_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{device}{number}" for device in ("COM", "LPT") for number in range(10)}
)
# ':' covers drive letters, alternate data streams and URL schemes; '\' covers UNC
# and device prefixes. Forward slashes are the only separator accepted.
_FORBIDDEN_CHARS = frozenset(':\\*?"<>|')
_PATH_HINT = "use a repo-relative path with forward slashes, e.g. {}/snapshots/x.png"


def check_image_path(raw_path: str, image_dirs: tuple[str, ...] = IMAGE_DIRS) -> tuple[str, ...]:
    """Validate an image path as a string only, without touching the filesystem.

    Args:
        raw_path: Repo-relative, forward slashes, inside one of `image_dirs`.
        image_dirs: Allowed repo-relative folders.

    Returns:
        The path's parts, safe to join onto the repo root.

    Raises:
        SceneError: On anything else: absolute/drive/UNC paths, '..', ':', backslashes,
            device names, other extensions, or a folder outside `image_dirs`.
    """
    hint = _PATH_HINT.format(image_dirs[0] if image_dirs else "<folder>")
    has_bad_char = any(char in _FORBIDDEN_CHARS or ord(char) < ord(" ") for char in raw_path)
    if not raw_path or len(raw_path) > MAX_IMAGE_PATH_CHARS or has_bad_char:
        raise SceneError(f"invalid image path {raw_path[:80]!r}; {hint}")
    parts = tuple(raw_path.split("/"))
    if any(_is_unsafe_part(part) for part in parts):
        raise SceneError(f"invalid image path {raw_path!r}; {hint}")
    if PurePosixPath(raw_path).suffix.lower() not in IMAGE_SUFFIXES:
        raise SceneError(f"image must be one of {', '.join(IMAGE_SUFFIXES)}: {raw_path}")
    if not any(_is_inside(parts, folder) for folder in image_dirs):
        raise SceneError(f"image must be inside {', '.join(image_dirs)}: {raw_path}")
    return parts


def resolve_image_path(
    raw_path: str, repo_root: Path = REPO_ROOT, image_dirs: tuple[str, ...] = IMAGE_DIRS
) -> Path:
    """Check an image path, then resolve it and confirm it's an existing file in an allowed folder.

    Args:
        raw_path: As for check_image_path.
        repo_root: What the path is relative to.
        image_dirs: Allowed repo-relative folders.

    Returns:
        The resolved absolute path.

    Raises:
        SceneError: If check_image_path rejects it, a link or junction leads out of
            the allowed folders, or the file doesn't exist.
    """
    parts = check_image_path(raw_path, image_dirs)
    resolved = repo_root.joinpath(*parts).resolve()
    allowed_roots = [repo_root.joinpath(*folder.split("/")).resolve() for folder in image_dirs]
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise SceneError(f"image path leads outside {', '.join(image_dirs)}: {raw_path}")
    if not resolved.is_file():
        raise SceneError(f"image file not found: {raw_path}")
    return resolved


def _is_unsafe_part(part: str) -> bool:
    # Empty parts come from a leading '/', '//' or a trailing '/'. Windows silently
    # drops trailing dots and spaces, so "x.png." could alias something else.
    if part in ("", ".", "..") or part != part.rstrip(". "):
        return True
    return part.split(".")[0].strip().upper() in _DEVICE_NAMES


def _is_inside(parts: tuple[str, ...], folder: str) -> bool:
    folder_parts = tuple(folder.split("/"))
    return len(parts) > len(folder_parts) and parts[: len(folder_parts)] == folder_parts
