"""Load the vault package lazily and adapt it to the LoginFiller protocol.

The vault (tools/vault, package `vault`) is built separately. Once it is added as
a uv path dependency of this project, `import vault` succeeds and its module-level
functions (list_credentials, fill_login, has_filled_fields, scrub) are used.
Until then every credential tool reports "vault not installed".

Nothing here asks the vault for a secret: there is no resolve/reveal call. The
vault fills the page itself.
"""

import importlib
import logging
from collections.abc import Callable
from types import ModuleType
from typing import Any

from browser_tool.credentials.missing_vault import VAULT_NOT_INSTALLED, MissingVaultFiller
from browser_tool.credentials.types import CredentialInfo, FillResult, LoginFiller

logger = logging.getLogger(__name__)

VAULT_MODULE = "vault"
REQUIRED_FUNCTIONS = ("list_credentials", "fill_login", "has_filled_fields", "scrub")
VAULT_INCOMPATIBLE = "vault not installed (installed version lacks the LoginFiller API)"

Importer = Callable[[str], ModuleType]


class VaultModuleFiller:
    """LoginFiller over the vault module's functions, converting its result types."""

    def __init__(self, module: ModuleType):
        """Args: module: The imported vault module (has REQUIRED_FUNCTIONS)."""
        self._vault = module

    def list_credentials(self) -> list[CredentialInfo]:
        """Return the vault's credential metadata as our CredentialInfo."""
        return [_to_credential_info(item) for item in self._vault.list_credentials()]

    async def fill_login(
        self, page: Any, credential_id: str, *, submit: bool = False
    ) -> FillResult:
        """Delegate to vault.fill_login and convert its FillResult."""
        result = await self._vault.fill_login(page, credential_id, submit=submit)
        return FillResult(ok=bool(result.ok), reason=str(result.reason))

    async def has_filled_fields(self, page: Any) -> bool:
        """Delegate to vault.has_filled_fields."""
        return bool(await self._vault.has_filled_fields(page))

    def scrub(self, page: Any, text: str) -> str:
        """Delegate to vault.scrub."""
        return str(self._vault.scrub(page, text))


class LazyVaultFiller:
    """LoginFiller that imports the vault on first use, then delegates to it."""

    def __init__(self, importer: Importer = importlib.import_module):
        """Args: importer: Module importer; tests pass a fake."""
        self._importer = importer
        self._delegate: LoginFiller | None = None

    def _filler(self) -> LoginFiller:
        if self._delegate is None:
            self._delegate = load_vault_filler(self._importer)
        return self._delegate

    def list_credentials(self) -> list[CredentialInfo]:
        """See LoginFiller.list_credentials."""
        return self._filler().list_credentials()

    async def fill_login(
        self, page: Any, credential_id: str, *, submit: bool = False
    ) -> FillResult:
        """See LoginFiller.fill_login."""
        return await self._filler().fill_login(page, credential_id, submit=submit)

    async def has_filled_fields(self, page: Any) -> bool:
        """See LoginFiller.has_filled_fields."""
        return await self._filler().has_filled_fields(page)

    def scrub(self, page: Any, text: str) -> str:
        """See LoginFiller.scrub."""
        return self._filler().scrub(page, text)


def load_vault_filler(importer: Importer = importlib.import_module) -> LoginFiller:
    """Import the vault and wrap it, or return a MissingVaultFiller saying why not."""
    try:
        module = importer(VAULT_MODULE)
    except ImportError as error:
        # Log only the exception type: import errors don't hold secrets, but stay terse.
        logger.info("vault unavailable (%s); credential tools disabled", type(error).__name__)
        return MissingVaultFiller(VAULT_NOT_INSTALLED)
    missing = [name for name in REQUIRED_FUNCTIONS if not callable(getattr(module, name, None))]
    if missing:
        logger.warning("vault lacks %s; credential tools disabled", ", ".join(missing))
        return MissingVaultFiller(VAULT_INCOMPATIBLE)
    return VaultModuleFiller(module)


def _to_credential_info(item: Any) -> CredentialInfo:
    # vault.models.CredentialInfo calls the display name `name`; we call it `label`.
    return CredentialInfo(
        id=str(item.id),
        label=str(item.name),
        origins=tuple(str(origin) for origin in item.origins),
        username_hint=str(item.username_hint),
    )
