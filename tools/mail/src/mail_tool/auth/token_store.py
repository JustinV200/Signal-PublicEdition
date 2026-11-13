"""TokenStore: one DPAPI-encrypted file per signed-in account, `.state/accounts/<alias>.bin`.

Each file holds {"email", "refresh_token"} as JSON, encrypted for the current
Windows user and locked to that user's ACL. Access tokens are never written to
disk; they live only in memory (see sessions.py).
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from mail_tool.auth import dpapi
from mail_tool.auth.owner_acl import restrict_to_owner
from mail_tool.errors import AccountError, ReauthRequired

BLOB_SUFFIX = ".bin"
# Binds blobs to this tool, so another DPAPI user of the same account can't be fed them.
DPAPI_ENTROPY = b"signal/tools/mail/refresh-token/v1"
# Aliases become file names, so they're kept to a short, path-safe set.
ALIAS_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


@dataclass(frozen=True)
class AccountRecord:
    """One signed-in account. repr() leaves out the refresh token."""

    alias: str
    email: str
    refresh_token: str = field(repr=False)


def normalize_alias(alias: str) -> str:
    """Lower-case and validate an alias.

    Raises:
        AccountError: It isn't 1-32 of a-z, 0-9, '-' or '_' (starting with a letter or digit).
    """
    cleaned = alias.strip().lower()
    if not ALIAS_PATTERN.fullmatch(cleaned):
        raise AccountError(
            f"Invalid alias {alias!r}: use 1-32 lowercase letters, digits, '-' or '_'."
        )
    return cleaned


class TokenStore:
    """Saves, loads and finds AccountRecords in one folder."""

    def __init__(self, folder: Path) -> None:
        """Args: folder: where the <alias>.bin files live (created on first save)."""
        self._folder = folder

    def save(self, record: AccountRecord) -> None:
        """Encrypt and write a record, replacing any earlier one with the same alias.

        Raises:
            AccountError: The alias is invalid.
            OSError, dpapi.DpapiError: The file couldn't be written or encrypted.
        """
        path = self._path(record.alias)
        plain = json.dumps({"email": record.email, "refresh_token": record.refresh_token})
        _write_atomically(path, dpapi.protect(plain.encode("utf-8"), DPAPI_ENTROPY))

    def load(self, alias: str) -> AccountRecord:
        """Read and decrypt one account.

        Raises:
            AccountError: No account has this alias.
            ReauthRequired: The file can't be decrypted or parsed.
        """
        path = self._path(alias)
        try:
            blob = path.read_bytes()
        except FileNotFoundError:
            raise AccountError(self._unknown_message(alias)) from None
        try:
            data = json.loads(dpapi.unprotect(blob, DPAPI_ENTROPY).decode("utf-8"))
            return AccountRecord(path.stem, str(data["email"]), str(data["refresh_token"]))
        except (dpapi.DpapiError, ValueError, KeyError, TypeError):
            # from None: the decrypted text (if any) must not ride along in the chain.
            raise ReauthRequired(path.stem, "The saved sign-in can't be decrypted") from None

    def remove(self, alias: str) -> bool:
        """Delete an account's file. Returns False when there was none."""
        path = self._path(alias)
        if not path.exists():
            return False
        path.unlink()
        return True

    def aliases(self) -> list[str]:
        """Every saved alias, sorted."""
        if not self._folder.is_dir():
            return []
        return sorted(p.stem for p in self._folder.glob(f"*{BLOB_SUFFIX}") if p.is_file())

    def find(self, account: str) -> AccountRecord:
        """Load an account by alias or by email address (case-insensitive).

        Raises:
            AccountError: Nothing matches.
            ReauthRequired: The matching alias's file can't be decrypted.
        """
        if "@" not in account:
            return self.load(account)
        wanted = account.strip().lower()
        for alias in self.aliases():
            try:
                record = self.load(alias)
            except ReauthRequired:
                continue  # its email can't be read; asking for it by alias gives the re-auth error
            if record.email.lower() == wanted:
                return record
        raise AccountError(self._unknown_message(account))

    def _path(self, alias: str) -> Path:
        return self._folder / f"{normalize_alias(alias)}{BLOB_SUFFIX}"

    def _unknown_message(self, account: str) -> str:
        known = ", ".join(self.aliases()) or "none yet (the owner adds one with `mail add`)"
        return f"No mail account {account!r}. Known accounts: {known}."


def _write_atomically(path: Path, blob: bytes) -> None:
    """Replace `path` with `blob` so a crash leaves the old file or the new one, never half.

    The temp file sits in the same folder and is locked to the owner before the
    secret goes in. os.replace is a rename, so the final file keeps that ACL.
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
