"""Crypto primitives for the vault: AES-GCM sealing, KDFs, DPAPI, canonical AAD, wiping.

Nothing here knows about credentials or files; `vault.store` builds on it.
"""

from vault.crypto.aad import canonical_json
from vault.crypto.aead import (
    KEY_BYTES,
    NONCE_BYTES,
    DecryptionError,
    Sealed,
    generate_key,
    open_sealed,
    seal,
)
from vault.crypto.dpapi import DpapiError
from vault.crypto.kdf import ScryptParams, hkdf_sha256, scrypt_key
from vault.crypto.wipe import wipe

__all__ = [
    "KEY_BYTES",
    "NONCE_BYTES",
    "DecryptionError",
    "DpapiError",
    "ScryptParams",
    "Sealed",
    "canonical_json",
    "generate_key",
    "hkdf_sha256",
    "open_sealed",
    "scrypt_key",
    "seal",
    "wipe",
]
