"""Public API of browser_tool.credentials: the vault contract and its adapters."""

from browser_tool.credentials.formatting import (
    FILL_OK,
    format_credentials,
    format_fill_result,
    safe_reason,
)
from browser_tool.credentials.missing_vault import VAULT_NOT_INSTALLED, MissingVaultFiller
from browser_tool.credentials.types import (
    CredentialInfo,
    FillResult,
    LoginFiller,
    VaultUnavailableError,
)
from browser_tool.credentials.vault_loader import LazyVaultFiller, load_vault_filler

__all__ = [
    "FILL_OK",
    "VAULT_NOT_INSTALLED",
    "CredentialInfo",
    "FillResult",
    "LazyVaultFiller",
    "LoginFiller",
    "MissingVaultFiller",
    "VaultUnavailableError",
    "format_credentials",
    "format_fill_result",
    "load_vault_filler",
    "safe_reason",
]
