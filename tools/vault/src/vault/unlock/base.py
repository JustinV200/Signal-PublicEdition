"""The `Unlocker` interface: how the vault gets its key-encryption key (KEK) from a human.

Every fill and every `vault add` asks an unlocker for the KEK, uses it to unwrap
the data key once, and wipes both. There is no unlock window. Which unlocker a
vault uses is fixed at `vault init` and bound into the wrapped data key's AAD,
so it can't be silently downgraded.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

PROVIDER_HELLO = "hello"
PROVIDER_PASSPHRASE = "passphrase"
PROVIDERS = (PROVIDER_HELLO, PROVIDER_PASSPHRASE)


class UnlockError(Exception):
    """The owner cancelled, the factor was unavailable or wrong, or the params were invalid."""


@dataclass(frozen=True)
class Enrollment:
    """What `Unlocker.enroll` produces at `vault init`.

    Attributes:
        unlock_params: JSON-safe, non-secret parameters stored in the vault file and
            handed back to `derive_kek` later (e.g. scrypt costs, a DPAPI blob).
        kek: The key-encryption key, as a bytearray the caller wipes.
    """

    unlock_params: dict[str, Any]
    kek: bytearray


class Unlocker(Protocol):
    """Turns a human factor plus the per-vault challenge into the KEK."""

    provider: str

    async def enroll(self, challenge: bytes) -> Enrollment:
        """Set up the factor for a new vault and return its params and first KEK.

        Raises:
            UnlockError: The factor is unavailable or the owner cancelled.
        """
        ...

    async def derive_kek(self, challenge: bytes, unlock_params: Mapping[str, Any]) -> bytearray:
        """Ask the owner for the factor and derive the KEK (caller wipes it).

        Raises:
            UnlockError: Cancelled, unavailable, or invalid params.
        """
        ...
