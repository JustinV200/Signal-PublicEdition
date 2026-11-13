"""Shared-secret token files for loopback IPC: create one, read one, compare one.

A loopback port alone doesn't stop other local processes, or a web page
POSTing text/plain to 127.0.0.1, from sending requests. So each server writes
a random token to a file only its owner can read, and every request must
carry it. The daemon creates its own token here and its clients read it. (The
audiohub voice hub publishes its kernel's token the same way; signal_hub_notify
reads that one.)
"""

import getpass
import hmac
import logging
import os
import secrets
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32
ENCODING = "ascii"
OWNER_ONLY_MODE = 0o600


def create_token_file(path: Path) -> str:
    """Write a fresh random token to path, readable by the current user only.

    The file is created and locked down before the secret goes in, so the
    token is never readable under the folder's inherited permissions.

    Args:
        path: Where to write it; the folder is created if needed.

    Returns:
        The new token.

    Raises:
        OSError: The file couldn't be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    _restrict_to_owner(path)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path.write_text(token, encoding=ENCODING)
    return token


def read_token(path: Path) -> str | None:
    """Read a token file.

    Args:
        path: The token file.

    Returns:
        The token, or None when the file is missing, unreadable or empty
        (the server that writes it isn't running).
    """
    try:
        token = path.read_text(encoding=ENCODING).strip()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        logger.warning("Can't read token file %s: %s", path, error)
        return None
    return token or None


def tokens_match(given: object, expected: str) -> bool:
    """Compare a request's token with the expected one in constant time.

    Args:
        given: The token from the request (any JSON value).
        expected: The server's token.

    Returns:
        True only for a string equal to expected.
    """
    if not isinstance(given, str):
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def _restrict_to_owner(path: Path) -> None:
    """Limit the file to the current user; log (don't fail) if that isn't possible."""
    if os.name != "nt":
        path.chmod(OWNER_ONLY_MODE)
        return
    user = getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{user}" if domain else user
    # Drop inherited entries and grant full control to this user alone.
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        logger.warning(
            "Couldn't restrict %s to %s (icacls: %s); other local users may read the token",
            path,
            account,
            (completed.stdout + completed.stderr).strip(),
        )
