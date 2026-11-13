"""Windows Hello unlock: a TPM-backed key signs the per-vault challenge; HKDF makes it the KEK.

This is the KeePassXC quick-unlock approach. It relies on the Hello key's
signatures being deterministic (RSA PKCS#1 v1.5 is), so `enroll` signs twice
and refuses the vault if the two signatures differ, instead of creating a vault
that could never be opened again.

The platform calls sit behind `HelloSigner` so this logic is testable without
a Hello device; `hello_winrt.WinRtHelloSigner` is the real one.
"""

import hmac
from collections.abc import Mapping
from typing import Any, Protocol

from vault.crypto import hkdf_sha256, wipe
from vault.unlock.base import PROVIDER_HELLO, Enrollment, UnlockError

# Name of the KeyCredential in the owner's Hello key store.
HELLO_KEY_NAME = "signal-vault"
HELLO_KEY_NAME_PARAM = "key_name"
# HKDF context label; changing it changes every derived key.
HELLO_KEK_INFO = b"signal-vault/v1/kek/hello"


class HelloSigner(Protocol):
    """Platform access to a named Windows Hello key."""

    async def create_key(self, key_name: str) -> None:
        """Create (or replace) the key, prompting the owner. Raises UnlockError on failure."""
        ...

    async def sign(self, key_name: str, challenge: bytes) -> bytearray:
        """Sign `challenge`, prompting the owner. Raises UnlockError on failure."""
        ...


class HelloUnlocker:
    """`Unlocker` backed by a Windows Hello `KeyCredential`."""

    provider = PROVIDER_HELLO

    def __init__(self, signer: HelloSigner | None = None) -> None:
        """Create the unlocker.

        Args:
            signer: The platform signer; defaults to the real WinRT one (imported lazily).
        """
        if signer is None:
            from vault.unlock.hello_winrt import WinRtHelloSigner

            signer = WinRtHelloSigner()
        self._signer = signer

    async def enroll(self, challenge: bytes) -> Enrollment:
        """Create the Hello key, check it signs deterministically, and return the first KEK.

        Raises:
            UnlockError: Hello unavailable, cancelled, or signatures not deterministic.
        """
        await self._signer.create_key(HELLO_KEY_NAME)
        first = await self._signer.sign(HELLO_KEY_NAME, challenge)
        second = await self._signer.sign(HELLO_KEY_NAME, challenge)
        try:
            if not hmac.compare_digest(bytes(first), bytes(second)):
                raise UnlockError(
                    "Windows Hello signatures are not deterministic here; "
                    "run `vault init --unlock passphrase` instead"
                )
            kek = _kek_from_signature(first, challenge)
        finally:
            wipe(first)
            wipe(second)
        return Enrollment(unlock_params={HELLO_KEY_NAME_PARAM: HELLO_KEY_NAME}, kek=kek)

    async def derive_kek(self, challenge: bytes, unlock_params: Mapping[str, Any]) -> bytearray:
        """Prompt for Hello, sign the challenge and derive the KEK.

        Raises:
            UnlockError: Unexpected params, Hello unavailable, or cancelled.
        """
        if dict(unlock_params) != {HELLO_KEY_NAME_PARAM: HELLO_KEY_NAME}:
            raise UnlockError("unexpected Windows Hello parameters in the vault file")
        signature = await self._signer.sign(HELLO_KEY_NAME, challenge)
        try:
            return _kek_from_signature(signature, challenge)
        finally:
            wipe(signature)


def _kek_from_signature(signature: bytearray, challenge: bytes) -> bytearray:
    """HKDF-SHA256 the signature into the KEK, salted with the per-vault challenge."""
    if not signature:
        raise UnlockError("Windows Hello returned an empty signature")
    return hkdf_sha256(signature, salt=challenge, info=HELLO_KEK_INFO)
