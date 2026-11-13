"""The LoginFiller used when the vault package isn't installed or isn't usable.

Credential tools report the reason ("vault not installed"); snapshot and
screenshot work normally because nothing can have been filled.
"""

from typing import Any

from browser_tool.credentials.types import CredentialInfo, FillResult, VaultUnavailableError

VAULT_NOT_INSTALLED = "vault not installed"


class MissingVaultFiller:
    """LoginFiller stand-in whose credential calls raise VaultUnavailableError."""

    def __init__(self, reason: str = VAULT_NOT_INSTALLED):
        """Args: reason: The text the credential tools return to the model."""
        self.reason = reason

    def list_credentials(self) -> list[CredentialInfo]:
        """Raises VaultUnavailableError(reason)."""
        raise VaultUnavailableError(self.reason)

    async def fill_login(
        self, page: Any, credential_id: str, *, submit: bool = False
    ) -> FillResult:
        """Raises VaultUnavailableError(reason)."""
        raise VaultUnavailableError(self.reason)

    async def has_filled_fields(self, page: Any) -> bool:
        """Nothing can be filled without a vault."""
        return False

    def scrub(self, page: Any, text: str) -> str:
        """No secrets to scrub without a vault."""
        return text
