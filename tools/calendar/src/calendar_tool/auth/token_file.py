"""The one stored calendar sign-in: `.state/token.bin`, DPAPI-encrypted, owner-only.

The file holds {"email", "refresh_token", "scopes"} as JSON, encrypted for the
current Windows user with calendar-specific entropy and written atomically (see
signal_googleauth). A file without "scopes" was saved by the read-only tool and
holds LEGACY_SCOPES. Access tokens are never written to disk.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from signal_googleauth import DpapiError, protect, unprotect, write_secret_atomically

from calendar_tool.auth.scopes import LEGACY_SCOPES
from calendar_tool.errors import ReauthRequired, SetupError

# Binds the blob to this tool, so mail's token files can't be swapped in (or the reverse).
DPAPI_ENTROPY = b"signal/tools/calendar/refresh-token/v1"


@dataclass(frozen=True)
class StoredSignIn:
    """The signed-in account and the scopes it was granted. repr() leaves out the token."""

    email: str
    refresh_token: str = field(repr=False)
    scopes: tuple[str, ...] = LEGACY_SCOPES


def save_sign_in(path: Path, sign_in: StoredSignIn) -> None:
    """Encrypt and write the sign-in, replacing any earlier one.

    Raises:
        OSError, DpapiError: The file couldn't be written or encrypted.
    """
    plain = json.dumps(
        {
            "email": sign_in.email,
            "refresh_token": sign_in.refresh_token,
            "scopes": list(sign_in.scopes),
        }
    )
    write_secret_atomically(path, protect(plain.encode("utf-8"), DPAPI_ENTROPY))


def load_sign_in(path: Path) -> StoredSignIn:
    """Read and decrypt the sign-in.

    Raises:
        SetupError: Nobody has signed in yet.
        ReauthRequired: The file can't be read, decrypted or parsed.
    """
    try:
        blob = path.read_bytes()
    except FileNotFoundError:
        raise SetupError("Not signed in yet. Run `calendar add`.") from None
    except OSError:
        raise ReauthRequired("The saved sign-in can't be read") from None
    try:
        data = json.loads(unprotect(blob, DPAPI_ENTROPY).decode("utf-8"))
        scopes = tuple(str(scope) for scope in data.get("scopes", LEGACY_SCOPES))
        return StoredSignIn(str(data["email"]), str(data["refresh_token"]), scopes)
    except (DpapiError, ValueError, KeyError, TypeError, AttributeError):
        # from None: the decrypted text (if any) must not ride along in the chain.
        raise ReauthRequired("The saved sign-in can't be decrypted") from None
