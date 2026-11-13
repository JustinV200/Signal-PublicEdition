"""write_owner_only: replace a secret file so it is never half-written or readable by others.

The temp file is locked to the current Windows user (icacls) before the secret
goes in, and renamed over the target, so the final file keeps that ACL. Unlike
the copy in packages/googleauth (owner_acl.py, secret_file.py), a failed ACL
refuses the write instead of logging and carrying on: these are live cookies.
"""

import getpass
import os
import subprocess
import tempfile
from pathlib import Path

ICACLS = "icacls"


def write_owner_only(path: Path, blob: bytes) -> None:
    """Replace `path` with `blob`, owner-only, so a crash leaves the old file or the new one.

    Args:
        path: The file to write (its folder is created if missing).
        blob: The bytes, a DPAPI blob.

    Raises:
        OSError: The file couldn't be written or locked to the owner (nothing
            is written then).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp"
    )
    os.close(descriptor)
    temp = Path(temp_name)
    try:
        _restrict_to_owner(temp)
        with temp.open("wb") as file:
            file.write(blob)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)  # already gone after a successful replace


def _restrict_to_owner(path: Path) -> None:
    """Drop inherited ACL entries and grant full control to the current user alone.

    Raises:
        OSError: icacls failed (its output, which names only the path, is in the message).
    """
    domain = os.environ.get("USERDOMAIN")
    user = getpass.getuser()
    account = f"{domain}\\{user}" if domain else user
    command = [ICACLS, str(path), "/inheritance:r", "/grant:r", f"{account}:F"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise OSError(f"icacls couldn't restrict {path.name} to {account}")
