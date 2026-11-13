"""Lazy vault loading with fake importers and a fake vault module."""

import types
from dataclasses import dataclass

import pytest
from vault.models import CredentialInfo as VaultCredential

from browser_tool.credentials import (
    VAULT_NOT_INSTALLED,
    FillResult,
    LazyVaultFiller,
    VaultUnavailableError,
    load_vault_filler,
)


def missing_importer(name: str) -> types.ModuleType:
    raise ModuleNotFoundError(f"No module named {name!r}", name=name)


@dataclass
class VaultResult:
    ok: bool
    reason: str


def fake_vault_module() -> types.ModuleType:
    module = types.ModuleType("vault")

    async def fill_login(page, credential_id, *, submit=False):
        return VaultResult(ok=True, reason="filled")

    async def has_filled_fields(page):
        return True

    # The real vault type, so a field rename on either side fails here (it once
    # read .label/.has_totp, which vault's CredentialInfo never had).
    credential = VaultCredential(
        id="gh", name="GitHub", origins=("https://github.com",), username_hint="j***"
    )
    module.list_credentials = lambda: [credential]
    module.fill_login = fill_login
    module.has_filled_fields = has_filled_fields
    module.scrub = lambda page, text: text.replace("pw", "[x]")
    return module


@pytest.mark.asyncio
async def test_missing_vault_reports_not_installed():
    filler = LazyVaultFiller(importer=missing_importer)
    with pytest.raises(VaultUnavailableError, match=VAULT_NOT_INSTALLED):
        filler.list_credentials()
    with pytest.raises(VaultUnavailableError):
        await filler.fill_login(None, "gh")
    assert await filler.has_filled_fields(None) is False
    assert filler.scrub(None, "text") == "text"


def test_vault_without_the_protocol_is_reported_incompatible():
    filler = load_vault_filler(importer=lambda name: types.ModuleType(name))
    with pytest.raises(VaultUnavailableError, match="lacks the LoginFiller API"):
        filler.list_credentials()


@pytest.mark.asyncio
async def test_vault_module_is_adapted_to_our_types():
    filler = LazyVaultFiller(importer=lambda name: fake_vault_module())
    [credential] = filler.list_credentials()
    assert (credential.id, credential.label, credential.origins) == (
        "gh",
        "GitHub",
        ("https://github.com",),
    )
    assert await filler.fill_login(None, "gh", submit=True) == FillResult(ok=True, reason="filled")
    assert await filler.has_filled_fields(None) is True
    assert filler.scrub(None, "my pw") == "my [x]"


def test_vault_is_imported_only_on_first_use():
    imported: list[str] = []

    def importer(name: str) -> types.ModuleType:
        imported.append(name)
        return fake_vault_module()

    filler = LazyVaultFiller(importer=importer)
    assert imported == []
    filler.list_credentials()
    filler.list_credentials()
    assert imported == ["vault"]
