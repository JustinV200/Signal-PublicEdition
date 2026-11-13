"""vault: fills web logins for Claude without any secret reaching the model.

SECURITY-SENSITIVE PACKAGE: changes here need the owner's review (see README.md).

Public API (used in-process by tools/browser):
    list_credentials() -> list[CredentialInfo]
    async fill_login(page, credential_id, *, submit=False) -> FillResult
    async has_filled_fields(page) -> bool
    scrub(page, text) -> str

There is deliberately no function that returns a secret.
"""

from vault.api import fill_login, has_filled_fields, list_credentials, scrub
from vault.models import CredentialInfo, FillResult

__all__ = [
    "CredentialInfo",
    "FillResult",
    "fill_login",
    "has_filled_fields",
    "list_credentials",
    "scrub",
]
