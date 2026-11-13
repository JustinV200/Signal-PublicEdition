"""Read and write the console's files in .state/: JSON records and owner-only secrets.

The .state folder holds the claimed session's inbox token, the local key and
conversation history, so it is locked to the current user whenever it's
ensured (at each start), and each secret file is locked again before its
secret goes in. A lock that fails raises, so a secret never lands in a file
other users can read. Stdlib only (the turn hook imports it).
"""

import getpass
import json
import os
import secrets
import subprocess
from pathlib import Path
from typing import Any

# 32 random bytes, URL-safe base64: plenty against guessing over loopback.
SECRET_BYTES = 32
OWNER_ONLY_MODE = 0o600


def ensure_state_dir(state_dir: Path) -> None:
    """Create the state folder if missing and lock it to the current user (children inherit it).

    The lock is re-applied on every call, so a folder whose permissions were
    loosened is locked again at the next start. It costs an icacls run on
    Windows, so call it at startup and before rare writes, not per event.

    Raises:
        OSError: The folder couldn't be created or locked.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    restrict_to_owner(state_dir, is_dir=True)


def read_json(path: Path) -> dict[str, Any] | None:
    """A JSON object from a file, or None if it's missing, unreadable or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # RecursionError: nested too deep to parse
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict[str, Any], *, is_private: bool = False) -> None:
    """Write a JSON object, owner-only first when `is_private` (it holds a secret)."""
    ensure_state_dir(path.parent)
    if is_private:
        _lock_before_writing(path)
    path.write_text(json.dumps(payload), encoding="utf-8")


def new_secret() -> str:
    """A fresh random secret (URL-safe text)."""
    return secrets.token_urlsafe(SECRET_BYTES)


def write_secret(path: Path, secret: str) -> None:
    """Write a secret to a file that only the current user can read."""
    ensure_state_dir(path.parent)
    _lock_before_writing(path)
    path.write_text(secret, encoding="utf-8")


def read_secret(path: Path) -> str | None:
    """A secret file's contents, or None if it's missing or empty."""
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return secret or None


def _lock_before_writing(path: Path) -> None:
    # Lock the file down before the secret goes in, so it's never readable under
    # the folder's inherited permissions (Users / Authenticated Users on Windows).
    path.touch(exist_ok=True)
    restrict_to_owner(path)


def restrict_to_owner(path: Path, *, is_dir: bool = False) -> None:
    """Limit a file or folder to the current user.

    Same icacls sequence as tools/whiteboard's state_files.py (separate projects share no code).
    TODO: move this and the whiteboard/sessions copies into a shared packages/ module.

    Args:
        path: The file or folder.
        is_dir: Grant with (OI)(CI) so files created in the folder inherit owner-only access.

    Raises:
        OSError: It couldn't be restricted, so nothing secret may go in.
    """
    if os.name != "nt":
        path.chmod(0o700 if is_dir else OWNER_ONLY_MODE)
        return
    user = getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{user}" if domain else user
    grant = f"{account}:(OI)(CI)F" if is_dir else f"{account}:F"
    # Drop inherited entries and grant full control to this user alone.
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", grant]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        output = (completed.stdout + completed.stderr).strip()
        raise OSError(f"couldn't restrict {path} to {account} (icacls: {output})")
