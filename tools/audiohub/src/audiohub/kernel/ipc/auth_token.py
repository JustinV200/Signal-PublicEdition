"""The shared secret that proves an IPC request comes from a local audiohub client.

Binding to 127.0.0.1 is not enough on its own: any web page can POST to a
loopback port. So the running hub writes a random token to a file that only
the user can read, and every request must carry it. A browser can't read the
file, so it can't forge a request.
"""

import getpass
import hmac
import logging
import os
import secrets
import subprocess
from pathlib import Path

from audiohub.config import CACHE_DIR

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_PATH = CACHE_DIR / "ipc-token"
TOKEN_BYTES = 32
OWNER_ONLY_MODE = 0o600
ACL_TIMEOUT_S = 10.0


def create_token_file(path: Path) -> str:
    """Write a fresh random token to `path`, readable by the current user only.

    Args:
        path: Where to write it (normally `DEFAULT_TOKEN_PATH`).

    Returns:
        The token.

    Raises:
        OSError: If the file can't be written.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)  # a fresh file gets fresh permissions
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, OWNER_ONLY_MODE)
    with os.fdopen(descriptor, "w", encoding="ascii") as file:
        file.write(token)
    if os.name == "nt":
        restrict_to_current_user(path)
    return token


def read_token(path: Path) -> str:
    """Read the token a running hub wrote.

    Raises:
        FileNotFoundError: If there is no token file, or it is empty (no hub).
        OSError: If the file can't be read.
    """
    token = path.read_text(encoding="ascii").strip()
    if not token:
        raise FileNotFoundError(f"the IPC token file {path} is empty")
    return token


def remove_token_file(path: Path, token: str) -> None:
    """Delete the token file, unless another hub has since replaced it."""
    try:
        if path.read_text(encoding="ascii").strip() == token:
            path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        logger.exception("could not remove the IPC token file %s", path)


def tokens_match(given: object, expected: str) -> bool:
    """Compare a request's token with the hub's in constant time."""
    if not isinstance(given, str):
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def restrict_to_current_user(path: Path) -> None:
    """Windows ignores POSIX modes, so replace the inherited ACL with owner-only access.

    Shared with the hub's own pid record (loop/conversation/hub_record.py).

    Best effort: if icacls fails the file keeps the folder's default ACL
    (still only local accounts), and a warning says so.
    """
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=ACL_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("could not make %s owner-only (%s); it keeps default access", path, error)
