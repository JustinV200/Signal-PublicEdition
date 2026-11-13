"""Key derivation: HKDF-SHA256 for high-entropy inputs and scrypt for passphrases.

HKDF turns a Windows Hello signature (or a scrypt output combined with a DPAPI
secret) into the key-encryption key. scrypt stretches the owner's passphrase.
Its parameters are stored in the vault file, so they are bounds-checked before
use to stop a tampered file from demanding huge memory.
"""

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DERIVED_KEY_BYTES = 32

# scrypt memory use is about 128 * r * n bytes: 128 MiB for the defaults.
DEFAULT_SCRYPT_N = 2**17
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
MIN_SCRYPT_N = 2**14
MAX_SCRYPT_N = 2**18
MAX_SCRYPT_P = 4
# Covers the largest allowed setting (2**18, r=8: 256 MiB) with headroom.
# hashlib's own default (32 MiB) is too small for the defaults above.
SCRYPT_MAXMEM_BYTES = 320 * 1024 * 1024


@dataclass(frozen=True)
class ScryptParams:
    """scrypt cost parameters. Use `validated()` before trusting values read from disk."""

    n: int = DEFAULT_SCRYPT_N
    r: int = DEFAULT_SCRYPT_R
    p: int = DEFAULT_SCRYPT_P

    def validated(self) -> "ScryptParams":
        """Return self if the parameters are within the allowed bounds.

        Raises:
            ValueError: n is not a power of two in range, r is not 8, or p is out of range.
        """
        is_power_of_two = self.n > 0 and self.n & (self.n - 1) == 0
        if not (is_power_of_two and MIN_SCRYPT_N <= self.n <= MAX_SCRYPT_N):
            raise ValueError("scrypt n must be a power of two between 2**14 and 2**18")
        if self.r != DEFAULT_SCRYPT_R:
            raise ValueError("scrypt r must be 8")
        if not 1 <= self.p <= MAX_SCRYPT_P:
            raise ValueError("scrypt p must be between 1 and 4")
        return self


def hkdf_sha256(input_key: bytes | bytearray, *, salt: bytes, info: bytes) -> bytearray:
    """Derive a 32-byte key with HKDF-SHA256.

    Args:
        input_key: High-entropy input key material.
        salt: A per-vault random salt (the vault challenge).
        info: A context label that separates keys derived for different purposes.

    Returns:
        The derived key, as a bytearray the caller should wipe.
    """
    hkdf = HKDF(algorithm=hashes.SHA256(), length=DERIVED_KEY_BYTES, salt=salt, info=info)
    return bytearray(hkdf.derive(input_key))


def scrypt_key(passphrase: bytes | bytearray, *, salt: bytes, params: ScryptParams) -> bytearray:
    """Stretch a passphrase with scrypt, using an explicit `maxmem`.

    Args:
        passphrase: The UTF-8 passphrase bytes.
        salt: A per-vault random salt.
        params: Cost parameters (validated here).

    Returns:
        A 32-byte key, as a bytearray the caller should wipe.

    Raises:
        ValueError: The parameters are out of bounds.
    """
    checked = params.validated()
    derived = hashlib.scrypt(
        passphrase,
        salt=salt,
        n=checked.n,
        r=checked.r,
        p=checked.p,
        maxmem=SCRYPT_MAXMEM_BYTES,
        dklen=DERIVED_KEY_BYTES,
    )
    return bytearray(derived)
