"""AES-256-GCM sealing with a fresh random nonce for every encryption.

Used twice in the store: the key-encryption key wraps the data key, and the
data key seals each credential. Both pass canonical-JSON metadata as AAD, so a
changed origin, policy or provider makes decryption fail.
"""

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BITS = 256
KEY_BYTES = KEY_BITS // 8


class DecryptionError(Exception):
    """The key, ciphertext or associated data did not verify."""


@dataclass(frozen=True)
class Sealed:
    """One AES-GCM output: the nonce and the ciphertext (with its tag appended)."""

    nonce: bytes
    ciphertext: bytes


def generate_key() -> bytearray:
    """Return a new random 256-bit key as a bytearray, so the caller can wipe it."""
    return bytearray(AESGCM.generate_key(bit_length=KEY_BITS))


def seal(key: bytes | bytearray, plaintext: bytes | bytearray, aad: bytes) -> Sealed:
    """Encrypt `plaintext` under `key` with a new `os.urandom` nonce.

    Args:
        key: A 32-byte AES key.
        plaintext: The bytes to protect.
        aad: Associated data that must match exactly on decryption.

    Returns:
        The nonce and ciphertext.

    Raises:
        ValueError: The key is not a valid AES key size.
    """
    _require_key_size(key)
    nonce = os.urandom(NONCE_BYTES)
    return Sealed(nonce=nonce, ciphertext=AESGCM(key).encrypt(nonce, plaintext, aad))


def open_sealed(key: bytes | bytearray, sealed: Sealed, aad: bytes) -> bytes:
    """Decrypt and verify `sealed`.

    Args:
        key: The 32-byte AES key it was sealed with.
        sealed: The nonce and ciphertext.
        aad: The associated data it was sealed with.

    Returns:
        The plaintext.

    Raises:
        DecryptionError: Wrong key, tampered ciphertext, or different AAD.
    """
    _require_key_size(key)
    try:
        return AESGCM(key).decrypt(sealed.nonce, sealed.ciphertext, aad)
    except InvalidTag:
        # InvalidTag carries no data, so dropping it loses nothing.
        raise DecryptionError("ciphertext or associated data did not verify") from None


def _require_key_size(key: bytes | bytearray) -> None:
    """Refuse anything but a 256-bit key, so a short key can never slip through."""
    if len(key) != KEY_BYTES:
        raise ValueError(f"expected a {KEY_BYTES}-byte key")
