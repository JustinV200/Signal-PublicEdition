"""The real `HelloSigner`: Windows.Security.Credentials.KeyCredentialManager through pywinrt.

UNTESTED ON A HELLO PROMPT: the owner wasn't available when this was written,
so only `is_hello_supported()` has run on the real machine. The status
handling follows the WinRT docs; the unit tests cover `HelloUnlocker` with a
fake signer. See the README before relying on this path.
"""

from winrt.windows.security.credentials import (
    KeyCredentialCreationOption,
    KeyCredentialManager,
    KeyCredentialStatus,
)
from winrt.windows.security.cryptography import CryptographicBuffer

from vault.unlock.base import UnlockError
from vault.unlock.hello_focus import hello_prompt_in_front

# Owner-facing explanations for the KeyCredentialStatus codes.
_STATUS_MESSAGES = {
    KeyCredentialStatus.UNKNOWN_ERROR: "Windows Hello failed with an unknown error",
    KeyCredentialStatus.NOT_FOUND: "the vault's Windows Hello key was not found; re-run vault init",
    KeyCredentialStatus.USER_CANCELED: "Windows Hello was cancelled",
    KeyCredentialStatus.USER_PREFERS_PASSWORD: "Windows Hello was declined in favour of a password",
    KeyCredentialStatus.CREDENTIAL_ALREADY_EXISTS: "a Windows Hello key with that name exists",
    KeyCredentialStatus.SECURITY_DEVICE_LOCKED: "the security device (TPM) is locked out",
}


def _require_success(status: KeyCredentialStatus) -> None:
    """Raise UnlockError unless `status` is SUCCESS."""
    if status != KeyCredentialStatus.SUCCESS:
        raise UnlockError(_STATUS_MESSAGES.get(status, "Windows Hello failed"))


async def is_hello_supported() -> bool:
    """Return True if Windows Hello key credentials are set up on this machine."""
    return bool(await KeyCredentialManager.is_supported_async())


class WinRtHelloSigner:
    """`HelloSigner` that talks to the real Windows Hello key store."""

    async def create_key(self, key_name: str) -> None:
        """Create the named key, replacing any old one, after a Hello prompt.

        Raises:
            UnlockError: Hello unsupported, cancelled or failed.
        """
        if not await is_hello_supported():
            raise UnlockError("Windows Hello is not set up on this machine")
        with hello_prompt_in_front():
            created = await KeyCredentialManager.request_create_async(
                key_name, KeyCredentialCreationOption.REPLACE_EXISTING
            )
        _require_success(created.status)

    async def sign(self, key_name: str, challenge: bytes) -> bytearray:
        """Sign `challenge` with the named key after a Hello prompt.

        Returns:
            The signature, as a bytearray the caller wipes.

        Raises:
            UnlockError: Key missing, cancelled or failed.
        """
        opened = await KeyCredentialManager.open_async(key_name)
        _require_success(opened.status)
        data = CryptographicBuffer.create_from_byte_array(challenge)
        with hello_prompt_in_front():
            signed = await opened.credential.request_sign_async(data)
        _require_success(signed.status)
        # IBuffer supports the buffer protocol, so this copies straight into a bytearray.
        return bytearray(memoryview(signed.result))
