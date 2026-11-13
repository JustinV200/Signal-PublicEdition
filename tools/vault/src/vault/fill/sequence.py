"""The `fill_login` sequence: check, confirm, unlock, re-check, fill, audit.

1. Refuse if Playwright debug logging is on.
2. Load metadata (nothing decrypted) and find the credential.
3. Find exactly one visible password field (the vault picks fields itself).
4. Check the top-level and frame origins against the registered origins.
5. Ask the owner (native dialog: name + live origin, defaults to No).
6. Unlock (Hello or passphrase prompt), unwrap the data key, decrypt this
   one record (which verifies its AAD-bound origins), wipe the keys.
7. Re-check the origins on the same ElementHandles, then fill through them.
   A Locator would re-resolve on a page that navigated in between; a handle
   just fails.
8. Optionally press Enter, write one audit line, return a bare FillResult.

No exception leaves this module: any error becomes FillResult(False, "error")
without being logged, because Playwright errors can contain the filled value.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from vault.audit import EVENT_FILL
from vault.confirm import ConfirmRequest
from vault.crypto import DecryptionError
from vault.fill.deps import FillDeps
from vault.fill.environment import playwright_debug_enabled
from vault.fill.fields import LoginFields, find_login_fields
from vault.fill.origin_check import OriginCheck, check_field_origins
from vault.fill.page_protocol import PageLike
from vault.fill.safe_fill import fill_without_leaks, press_submit_without_leaks
from vault.models import (
    REASON_DENIED,
    REASON_ERROR,
    REASON_FILLED,
    REASON_LOCKED,
    REASON_NO_FIELDS,
    REASON_NOT_FOUND,
    REASON_ORIGIN_MISMATCH,
    REASON_TAMPERED,
    REASON_UNSAFE_ENVIRONMENT,
    FillResult,
)
from vault.store import (
    CredentialRecord,
    LoginSecrets,
    TamperedRecordError,
    VaultData,
    VaultHeader,
    VaultNotInitializedError,
    load_vault,
    open_credential,
    unlocked_dek,
)
from vault.unlock import UnlockError

RESULT_CANCELLED = "cancelled"


@dataclass
class _AuditOrigins:
    """Origin labels learned during the attempt, for the audit line."""

    top_origin: str = ""
    frame_origin: str = ""


async def fill_login_with(
    deps: FillDeps, page: PageLike, credential_id: str, *, submit: bool = False
) -> FillResult:
    """Fill the stored login `credential_id` into `page`, if every check passes.

    Args:
        deps: Store path, audit log, confirmer, unlocker factory, registry.
        page: A Playwright Page.
        credential_id: The id from `list_credentials()`.
        submit: Press Enter in the password field after filling.

    Returns:
        FillResult(ok, reason) with a fixed reason code. Never raises, except
        asyncio.CancelledError.
    """
    origins = _AuditOrigins()
    reason = REASON_ERROR
    try:
        reason = await _attempt(deps, page, credential_id, submit, origins)
    except asyncio.CancelledError:
        deps.audit.record(EVENT_FILL, credential_id, RESULT_CANCELLED, **vars(origins))
        raise
    except Exception:
        # Discarded without logging: it may be a Playwright error carrying a call log.
        reason = REASON_ERROR
    deps.audit.record(EVENT_FILL, credential_id, reason, **vars(origins))
    return FillResult(ok=reason == REASON_FILLED, reason=reason)


def _load_metadata(deps: FillDeps) -> VaultData | None:
    """Load store.json without decrypting anything; None if there is no vault yet."""
    try:
        return load_vault(deps.store_path)
    except VaultNotInitializedError:
        return None


async def _attempt(
    deps: FillDeps, page: PageLike, credential_id: str, submit: bool, origins: _AuditOrigins
) -> str:
    """Run steps 1-8 and return the reason code."""
    if playwright_debug_enabled():
        return REASON_UNSAFE_ENVIRONMENT
    data = _load_metadata(deps)
    record = data.find(credential_id) if data else None
    if data is None or record is None:
        return REASON_NOT_FOUND
    fields = await find_login_fields(page)
    if fields is None:
        return REASON_NO_FIELDS
    check = await _check_fields(page, fields, record.meta.origins)
    origins.top_origin, origins.frame_origin = check.top_origin, check.frame_origin
    if not check.ok:
        return REASON_ORIGIN_MISMATCH
    request = ConfirmRequest(record.meta.id, record.meta.name, check.top_origin, check.frame_origin)
    if not await deps.confirmer.confirm(request):
        return REASON_DENIED
    secrets = await _decrypt(deps, data.header, record)
    if isinstance(secrets, str):
        return secrets
    return await _fill_rechecked(deps, page, fields, record, secrets, submit)


async def _check_fields(page: PageLike, fields: LoginFields, allowed: Sequence[str]) -> OriginCheck:
    """Check the password field and any username field. Labels come from the password field."""
    check = await check_field_origins(page, fields.password, allowed)
    if check.ok and fields.username is not None:
        username_check = await check_field_origins(page, fields.username, allowed)
        if not username_check.ok:
            return OriginCheck(
                ok=False, top_origin=check.top_origin, frame_origin=check.frame_origin
            )
    return check


async def _decrypt(
    deps: FillDeps, header: VaultHeader, record: CredentialRecord
) -> LoginSecrets | str:
    """Unlock, decrypt one record and wipe the keys. Returns the secrets or a reason code."""
    try:
        unlocker = deps.unlocker_for(header.provider)
        async with unlocked_dek(header, unlocker) as dek:
            return open_credential(dek, header, record)
    except (UnlockError, DecryptionError):
        return REASON_LOCKED
    except TamperedRecordError:
        return REASON_TAMPERED


async def _fill_rechecked(
    deps: FillDeps,
    page: PageLike,
    fields: LoginFields,
    record: CredentialRecord,
    secrets: LoginSecrets,
    submit: bool,
) -> str:
    """Re-check origins on the same handles, register them, fill, and optionally submit."""
    targets = [(fields.password, secrets.password)]
    # A password-only credential leaves whatever is in the username box alone.
    if fields.username is not None and secrets.username.reveal():
        targets.insert(0, (fields.username, secrets.username))
    del secrets
    recheck = await _check_fields(page, fields, record.meta.origins)
    if not recheck.ok:
        return REASON_ORIGIN_MISMATCH
    # No await between the re-check above and the fill below except the fill itself.
    for handle, secret in targets:
        deps.registry.register(page, handle, secret)
    is_filled = await fill_without_leaks(targets)
    targets.clear()
    if not is_filled:
        return REASON_ERROR
    if submit and not await press_submit_without_leaks(fields.password):
        return REASON_ERROR
    return REASON_FILLED
