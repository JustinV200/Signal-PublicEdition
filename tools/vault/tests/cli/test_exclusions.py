"""Excluded-category heuristic: catches the risky kinds, doesn't flag ordinary sites."""

import pytest

from vault.cli.exclusions import excluded_category


@pytest.mark.parametrize(
    ("credential_id", "name", "origin", "category"),
    [
        ("work", "Work mail", "https://outlook.office.com", "email"),
        ("boa", "BofA", "https://www.bankofamerica.com", "financial"),
        ("dns", "Registrar", "https://dash.cloudflare.com", "registrar / DNS / cloud"),
        ("school", "School", "https://sso.example.edu", "SSO / identity"),
        ("taxes", "Taxes", "https://www.irs.gov", "government / health / tax"),
        ("forum", "Forum", "https://forum.example.test", None),
        ("shop", "Purchase portal", "https://shop.example.test", None),
    ],
)
def test_excluded_category(credential_id, name, origin, category):
    assert excluded_category(credential_id, name, [origin]) == category
