"""write_atomically: replace a file's bytes in one step, for every state file and the plan edit.

The new bytes go to a temp file next to the target, then os.replace swaps it in, so
a crash or a full disk never leaves scene.json, calibration.json, todo.json or the
owner's week plan half written.
"""

import os
from pathlib import Path

_TEMP_SUFFIX = ".whiteboard-tmp"


class FileChangedError(OSError):
    """The file no longer held the bytes it was read with, so it wasn't replaced."""


def write_atomically(path: Path, data: bytes, unchanged_from: bytes | None = None) -> None:
    """Write `data` to `path` through a temp file and a rename.

    Args:
        path: The file to replace (its folder must exist).
        data: The new contents.
        unchanged_from: If given, the bytes `path` was read with. It's read again
            right before the swap, and if someone else changed it meanwhile
            nothing is written, so their edit isn't lost.

    Raises:
        FileChangedError: `path` no longer holds `unchanged_from`.
        OSError: The folder isn't writable, or the file is locked by another program.
            The temp file is removed again in every case.
    """
    temp_path = path.with_name(path.name + _TEMP_SUFFIX)
    try:
        temp_path.write_bytes(data)
        if unchanged_from is not None and path.read_bytes() != unchanged_from:
            raise FileChangedError(f"{path} changed on disk while it was being edited")
        # race (narrow): a save landing between that re-read and this swap is still lost.
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
