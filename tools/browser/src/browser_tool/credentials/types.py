"""The LoginFiller contract between the browser tool and the vault (tools/vault).

The vault fills login forms itself, in-process; secrets never cross this
interface. The browser tool only learns ok/reason, whether a page currently holds
vault-filled fields, and gets text scrubbed of any secret filled on a page.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CredentialInfo:
    """Metadata that is safe to show the model. Never a password or full username."""

    id: str
    label: str
    origins: tuple[str, ...]
    username_hint: str


@dataclass(frozen=True)
class FillResult:
    """Outcome of a fill. `reason` is a short code such as "filled" or "origin_mismatch"."""

    ok: bool
    reason: str


class VaultUnavailableError(Exception):
    """The vault package is not installed or not usable; the message says which."""


class LoginFiller(Protocol):
    """What the browser tool needs from the vault. `page` is a Playwright Page."""

    def list_credentials(self) -> list[CredentialInfo]:
        """List credentials the model may refer to by id.

        Raises:
            VaultUnavailableError: If there is no usable vault.
        """
        ...

    async def fill_login(
        self, page: Any, credential_id: str, *, submit: bool = False
    ) -> FillResult:
        """Fill (and optionally submit) the login form on `page` for `credential_id`.

        Raises:
            VaultUnavailableError: If there is no usable vault.
        """
        ...

    async def has_filled_fields(self, page: Any) -> bool:
        """True while `page` holds vault-filled fields (snapshots/screenshots must refuse)."""
        ...

    def scrub(self, page: Any, text: str) -> str:
        """Return `text` with any secret filled on `page` removed."""
        ...
