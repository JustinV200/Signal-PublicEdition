"""In-memory shape of the vault file, and the AAD each part is bound to.

Layout: one `VaultHeader` (format version, unlock provider, per-vault random
challenge, unlock params, and the data key wrapped by the KEK) plus one
`CredentialRecord` per credential (plaintext metadata plus the sealed
username/password).

AAD is canonical JSON built from these same objects, so the metadata the fill
path checks is exactly the metadata decryption verifies.
"""

import base64
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vault.crypto import Sealed, canonical_json
from vault.models import CredentialInfo

FORMAT_VERSION = 1
MAX_NAME_CHARS = 100
CHALLENGE_BYTES = 32
# Lowercase, starts alphanumeric, up to 64 chars. Also safe to echo in logs.
CREDENTIAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
POLICY_CONFIRM_KEY = "confirm"
POLICY_CONFIRM_ALWAYS = "always"
POLICY_CONFIRM_NEVER = "never"
# The default asks on every fill. The policy is AAD-bound, so editing it in
# store.json makes the record undecryptable; only `vault policy` (which
# unlocks) can change it. The fill path skips the dialog only for exactly
# "never"; any other value asks.
DEFAULT_POLICY: Mapping[str, str] = {POLICY_CONFIRM_KEY: POLICY_CONFIRM_ALWAYS}


def b64(data: bytes) -> str:
    """Encode bytes as standard base64 text for the JSON file and for AAD."""
    return base64.b64encode(data).decode("ascii")


def header_aad(
    version: int, provider: str, challenge: bytes, unlock_params: Mapping[str, Any]
) -> bytes:
    """AAD for the wrapped data key: every header field except the wrapped key itself."""
    return canonical_json(
        {
            "challenge": b64(challenge),
            "provider": provider,
            "unlock_params": dict(unlock_params),
            "version": version,
        }
    )


@dataclass(frozen=True)
class VaultHeader:
    """Vault-wide settings and the wrapped data key."""

    version: int
    provider: str
    challenge: bytes
    unlock_params: Mapping[str, Any]
    wrapped_dek: Sealed

    def aad(self) -> bytes:
        """Return the AAD the data key was wrapped with."""
        return header_aad(self.version, self.provider, self.challenge, self.unlock_params)


@dataclass(frozen=True)
class CredentialMeta:
    """Plaintext metadata for one credential. Every field is bound into its ciphertext's AAD."""

    id: str
    name: str
    origins: tuple[str, ...]
    username_hint: str
    policy: Mapping[str, str]
    version: int = FORMAT_VERSION

    def aad(self, provider: str) -> bytes:
        """Return the AAD for this credential's ciphertext under a vault using `provider`."""
        return canonical_json(
            {
                "id": self.id,
                "name": self.name,
                "origins": list(self.origins),
                "policy": dict(self.policy),
                "provider": provider,
                "username_hint": self.username_hint,
                "version": self.version,
            }
        )

    def info(self) -> CredentialInfo:
        """Return the model-safe view of this credential."""
        return CredentialInfo(
            id=self.id, name=self.name, origins=self.origins, username_hint=self.username_hint
        )


@dataclass(frozen=True)
class CredentialRecord:
    """One stored credential: metadata plus the sealed {username, password} JSON."""

    meta: CredentialMeta
    sealed: Sealed


@dataclass(frozen=True)
class VaultData:
    """The whole vault file: header plus records in insertion order."""

    header: VaultHeader
    records: tuple[CredentialRecord, ...] = ()

    def find(self, credential_id: str) -> CredentialRecord | None:
        """Return the record with `credential_id`, or None."""
        return next((record for record in self.records if record.meta.id == credential_id), None)

    def with_record(self, record: CredentialRecord) -> "VaultData":
        """Return a copy with `record` appended. Raises ValueError if the id already exists."""
        if self.find(record.meta.id) is not None:
            raise ValueError(f"credential {record.meta.id!r} already exists")
        return VaultData(header=self.header, records=(*self.records, record))

    def without_record(self, credential_id: str) -> "VaultData":
        """Return a copy without `credential_id`. Raises KeyError if it doesn't exist."""
        if self.find(credential_id) is None:
            raise KeyError(credential_id)
        kept = tuple(record for record in self.records if record.meta.id != credential_id)
        return VaultData(header=self.header, records=kept)
