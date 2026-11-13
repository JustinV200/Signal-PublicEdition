"""The four public functions `tools/browser` calls, wired to the real store, dialogs and unlockers.

There is deliberately no function that returns a secret. The registry of
filled fields is process-wide, so the snapshot gate and the scrubber see every
fill this process made.
"""

from vault.audit import AuditLog
from vault.confirm import DialogConfirmer
from vault.fill import (
    FillDeps,
    FilledRegistry,
    fill_login_with,
    page_has_filled_fields,
    scrub_text,
)
from vault.fill.page_protocol import PageLike
from vault.models import CredentialInfo, FillResult
from vault.paths import default_audit_path, default_store_path
from vault.store import load_vault, vault_exists
from vault.unlock import unlocker_for

_REGISTRY = FilledRegistry()


def _default_deps() -> FillDeps:
    return FillDeps(
        store_path=default_store_path(),
        audit=AuditLog(default_audit_path()),
        confirmer=DialogConfirmer(),
        unlocker_for=unlocker_for,
        registry=_REGISTRY,
    )


def list_credentials() -> list[CredentialInfo]:
    """List stored credentials: id, name, origins and a username hint only.

    Returns:
        One entry per credential; empty if the vault isn't initialised.

    Raises:
        VaultFormatError: store.json is malformed.
    """
    store_path = default_store_path()
    if not vault_exists(store_path):
        return []
    return [record.meta.info() for record in load_vault(store_path).records]


async def fill_login(page: PageLike, credential_id: str, *, submit: bool = False) -> FillResult:
    """Fill a stored login into `page` after origin checks, owner confirmation and unlock.

    Args:
        page: A playwright.async_api.Page.
        credential_id: An id from `list_credentials()`.
        submit: Press Enter in the password field after filling.

    Returns:
        FillResult(ok, reason); reason is a fixed code (see vault.models). Never
        raises, except asyncio.CancelledError.
    """
    return await fill_login_with(_default_deps(), page, credential_id, submit=submit)


async def has_filled_fields(page: PageLike) -> bool:
    """Return True while a snapshot or screenshot of `page` could show a filled secret.

    The browser tool must refuse snapshot and screenshot while this is True.
    """
    return await page_has_filled_fields(page, _REGISTRY)


def scrub(page: PageLike, text: str) -> str:
    """Remove every username/password the vault filled from `text`.

    Scrubs the secrets of all open pages, not just `page`, so a value copied to
    another tab is still caught. `page` is kept for API symmetry.

    Args:
        page: The page the text came from.
        text: Text the browser tool is about to return to the model.

    Returns:
        The text with each filled value (and its JSON/URL/HTML encodings) replaced.
    """
    del page  # every open page's secrets are scrubbed; see the docstring
    return scrub_text(text, _REGISTRY.secrets())
