"""Makes the pip-installed NVIDIA cuBLAS/cuDNN DLLs loadable on Windows.

faster-whisper runs on CTranslate2. On first GPU use, CTranslate2 loads
cublas64_12.dll (and cuDNN's sub-libraries) with a plain LoadLibrary call. The
DLLs come from the `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` wheels, under
site-packages/nvidia/<lib>/bin. Tested here (ctranslate2 4.8.3):
`os.add_dll_directory` alone is NOT enough, because plain LoadLibrary searches
PATH. So each directory is registered both ways. The model loader calls this
before importing faster_whisper.
"""

import importlib.util
import logging
import os
import sys
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

# Namespace package that the nvidia-*-cu12 wheels install into.
NVIDIA_PACKAGE = "nvidia"

# Handles from os.add_dll_directory. Kept so the registrations stay
# discoverable and are never repeated within this process.
_registered: dict[Path, object] = {}


def find_nvidia_bin_dirs(search_roots: Iterable[Path] | None = None) -> list[Path]:
    """List the `<root>/<lib>/bin` directories that contain DLLs.

    Args:
        search_roots: Directories to search. Defaults to the install locations
            of the `nvidia` namespace package, or none if it isn't installed.

    Returns:
        Sorted, de-duplicated bin directories that hold at least one .dll.
    """
    roots = list(search_roots) if search_roots is not None else _nvidia_package_roots()
    bin_dirs = {
        bin_dir.resolve()
        for root in roots
        for bin_dir in root.glob("*/bin")
        if bin_dir.is_dir() and any(bin_dir.glob("*.dll"))
    }
    return sorted(bin_dirs)


def register_nvidia_dll_dirs(search_roots: Iterable[Path] | None = None) -> list[Path]:
    """Make the NVIDIA wheel DLLs findable by CTranslate2. No-op off Windows.

    Each bin directory is passed to `os.add_dll_directory` and prepended to
    PATH. Safe to call repeatedly: already-registered directories are skipped.

    Args:
        search_roots: Passed to `find_nvidia_bin_dirs`. Tests use it to point at
            fake directories.

    Returns:
        The directories newly registered by this call.
    """
    if sys.platform != "win32":
        return []
    new_dirs = [path for path in find_nvidia_bin_dirs(search_roots) if path not in _registered]
    for path in new_dirs:
        _registered[path] = os.add_dll_directory(str(path))
    if new_dirs:
        added = os.pathsep.join(str(path) for path in new_dirs)
        os.environ["PATH"] = added + os.pathsep + os.environ.get("PATH", "")
        logger.info("registered NVIDIA DLL directories: %s", added)
    elif not _registered:
        logger.warning("no NVIDIA DLL directories found; CUDA STT will likely fail")
    return new_dirs


def _nvidia_package_roots() -> list[Path]:
    spec = importlib.util.find_spec(NVIDIA_PACKAGE)
    if spec is None or spec.submodule_search_locations is None:
        return []
    return [Path(location) for location in spec.submodule_search_locations]
