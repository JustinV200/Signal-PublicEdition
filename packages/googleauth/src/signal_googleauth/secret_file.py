"""write_secret_atomically: replace a secret file so it is never half-written or readable by others.

Used for the DPAPI-encrypted token files of the mail and calendar tools.
"""

import os
import tempfile
from pathlib import Path

from signal_googleauth.owner_acl import restrict_to_owner


def write_secret_atomically(path: Path, blob: bytes) -> None:
    """Replace `path` with `blob` so a crash leaves the old file or the new one, never half.

    The temp file sits in the same folder and is locked to the owner before the
    secret goes in. os.replace is a rename, so the final file keeps that ACL.

    Args:
        path: The file to write (its folder is created if missing).
        blob: The bytes, usually a DPAPI blob.

    Raises:
        OSError: The file couldn't be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp"
    )
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        restrict_to_owner(temp)
        with temp.open("wb") as file:
            file.write(blob)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)  # already gone after a successful replace
