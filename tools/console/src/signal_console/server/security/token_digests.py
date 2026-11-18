"""The page session tokens' SHA-256 digests on disk, so open windows survive a server restart.

Only digests go in the file, never a token: a digest lets the restarted server
recognise a token it minted before, but can't be sent as one. The file is
locked to the current user before every write (state_files), and a lock that
fails fails the write.
"""

import hashlib
from pathlib import Path

from signal_console.state_files import read_json, write_json

DIGESTS_KEY = "digests"


def token_digest(token: str) -> str:
    """A token's SHA-256 digest as hex text.

    surrogatepass, as in secrets_match: a header that wasn't valid UTF-8 holds
    lone surrogates, which then hash (and fail to match) instead of raising.
    """
    return hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest()


def load_digests(path: Path) -> list[str]:
    """The saved digests, oldest first; [] if the file is missing or not in this shape."""
    digests = (read_json(path) or {}).get(DIGESTS_KEY)
    if not isinstance(digests, list):
        return []
    # A non-string can't go through the constant-time compare, so it's dropped here.
    return [digest for digest in digests if isinstance(digest, str)]


def save_digests(path: Path, digests: list[str]) -> None:
    """Replace the saved digests, owner-only.

    Raises:
        OSError: The file couldn't be locked (then nothing goes in) or written.
    """
    write_json(path, {DIGESTS_KEY: digests}, is_private=True)
