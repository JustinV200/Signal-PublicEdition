"""Passphrase unlock (the fallback chosen explicitly at `vault init`): scrypt combined with DPAPI.

KEK = HKDF-SHA256(scrypt(passphrase) || DPAPI-protected random secret), salted
with the per-vault challenge. The passphrase is the human gate (same-user code
can call DPAPI but doesn't know the passphrase); DPAPI ties the store to this
Windows account, so a copied disk image needs both.
"""

import asyncio
import base64
import binascii
import os
from collections.abc import Callable, Mapping
from typing import Any

from vault.crypto import ScryptParams, hkdf_sha256, scrypt_key, wipe
from vault.crypto.dpapi import DpapiError, protect, unprotect
from vault.unlock.base import PROVIDER_PASSPHRASE, Enrollment, UnlockError
from vault.unlock.passphrase_dialog import PassphraseRequest, ask_passphrase

PASSPHRASE_KEK_INFO = b"signal-vault/v1/kek/passphrase"
DPAPI_ENTROPY = b"signal-vault/v1/dpapi"
DPAPI_SECRET_BYTES = 32
MIN_PASSPHRASE_BYTES = 12

ENROLL_MESSAGE = (
    f"Choose a passphrase for the Signal vault (at least {MIN_PASSPHRASE_BYTES} characters).\n"
    "It is needed for every sign-in. It can't be recovered."
)
UNLOCK_MESSAGE = "Enter the Signal vault passphrase to allow this sign-in."

# A prompt takes a request and returns the passphrase bytes, or None if cancelled.
PassphrasePrompt = Callable[[PassphraseRequest], bytearray | None]


class PassphraseUnlocker:
    """`Unlocker` that asks for a passphrase in a native masked dialog."""

    provider = PROVIDER_PASSPHRASE

    def __init__(
        self, prompt: PassphrasePrompt = ask_passphrase, scrypt_params: ScryptParams | None = None
    ) -> None:
        """Create the unlocker.

        Args:
            prompt: Blocking passphrase prompt; run on a worker thread.
            scrypt_params: Cost parameters for new vaults (defaults to ScryptParams()).
        """
        self._prompt = prompt
        self._scrypt_params = (scrypt_params or ScryptParams()).validated()

    async def _ask(self, request: PassphraseRequest) -> bytearray:
        """Run the prompt off the event loop; raise UnlockError if cancelled."""
        passphrase = await asyncio.to_thread(self._prompt, request)
        if passphrase is None:
            raise UnlockError("the passphrase prompt was cancelled or timed out")
        return passphrase

    async def enroll(self, challenge: bytes) -> Enrollment:
        """Ask for a new passphrase (twice), create the DPAPI secret, and return the first KEK.

        Raises:
            UnlockError: Cancelled, too short, or DPAPI failed.
        """
        passphrase = await self._ask(
            PassphraseRequest(ENROLL_MESSAGE, confirm=True, min_length=MIN_PASSPHRASE_BYTES)
        )
        dpapi_secret = bytearray(os.urandom(DPAPI_SECRET_BYTES))
        try:
            if len(passphrase) < MIN_PASSPHRASE_BYTES:
                raise UnlockError(
                    f"the passphrase must be at least {MIN_PASSPHRASE_BYTES} characters"
                )
            blob = _dpapi_call(protect, dpapi_secret)
            kek = _combine(passphrase, dpapi_secret, challenge, self._scrypt_params)
        finally:
            wipe(passphrase)
            wipe(dpapi_secret)
        params = _params_to_json(self._scrypt_params, blob)
        return Enrollment(unlock_params=params, kek=kek)

    async def derive_kek(self, challenge: bytes, unlock_params: Mapping[str, Any]) -> bytearray:
        """Ask for the passphrase, unprotect the DPAPI secret, and derive the KEK.

        A wrong passphrase isn't detected here; it yields a wrong KEK, and the
        data-key unwrap then fails.

        Raises:
            UnlockError: Cancelled, invalid params, or DPAPI failed.
        """
        scrypt_params, blob = _params_from_json(unlock_params)
        dpapi_secret = _dpapi_call(unprotect, blob)
        passphrase = None
        try:
            passphrase = await self._ask(PassphraseRequest(UNLOCK_MESSAGE))
            return _combine(passphrase, dpapi_secret, challenge, scrypt_params)
        finally:
            wipe(passphrase)
            wipe(dpapi_secret)


def _dpapi_call(function: Callable[[Any, bytes], Any], data: Any) -> Any:
    """Run a DPAPI function with the vault's entropy, mapping failures to UnlockError."""
    try:
        return function(data, DPAPI_ENTROPY)
    except DpapiError:
        raise UnlockError("Windows DPAPI could not open the vault key for this user") from None


def _combine(
    passphrase: bytearray, dpapi_secret: bytearray, challenge: bytes, params: ScryptParams
) -> bytearray:
    """KEK = HKDF(scrypt(passphrase) || dpapi_secret), wiping every intermediate."""
    stretched = scrypt_key(passphrase, salt=challenge, params=params)
    material = stretched + dpapi_secret
    try:
        return hkdf_sha256(material, salt=challenge, info=PASSPHRASE_KEK_INFO)
    finally:
        wipe(stretched)
        wipe(material)


def _params_to_json(params: ScryptParams, dpapi_blob: bytes) -> dict[str, Any]:
    """Serialise the non-secret unlock params stored in the vault header."""
    return {
        "scrypt": {"n": params.n, "r": params.r, "p": params.p},
        "dpapi_blob": base64.b64encode(dpapi_blob).decode("ascii"),
    }


def _params_from_json(unlock_params: Mapping[str, Any]) -> tuple[ScryptParams, bytes]:
    """Parse and bounds-check the stored unlock params (they come from a file on disk)."""
    try:
        scrypt = unlock_params["scrypt"]
        params = ScryptParams(
            n=int(scrypt["n"]), r=int(scrypt["r"]), p=int(scrypt["p"])
        ).validated()
        blob = base64.b64decode(unlock_params["dpapi_blob"], validate=True)
    except (KeyError, TypeError, ValueError, binascii.Error):
        raise UnlockError("invalid passphrase parameters in the vault file") from None
    return params, blob
