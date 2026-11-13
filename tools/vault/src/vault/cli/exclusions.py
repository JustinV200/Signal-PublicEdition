"""Spot account categories that should stay out of the vault, so `vault add` can warn first.

Excluded (password-vault.md section 5): email, SSO/identity, financial,
password managers, registrar/DNS/cloud consoles, government/health/tax, and
admin or account-recovery accounts. These can reset or drain other accounts.
Matching is a keyword heuristic on the id, name and origin hosts: it warns,
the owner decides.
"""

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

# Distinctive names matched anywhere in the text (substring).
_SUBSTRING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "email": ("gmail", "outlook", "hotmail", "protonmail", "proton.me", "fastmail", "yahoo"),
    "SSO / identity": ("google", "microsoft", "apple", "icloud", "okta", "auth0", "onelogin"),
    "financial": (
        "paypal",
        "venmo",
        "stripe",
        "coinbase",
        "binance",
        "kraken",
        "robinhood",
        "fidelity",
        "schwab",
        "vanguard",
        "wellsfargo",
        "capitalone",
        "americanexpress",
        "wise.com",
        "revolut",
        "bank",
    ),
    "password manager": (
        "1password",
        "bitwarden",
        "lastpass",
        "dashlane",
        "keepass",
        "keepersecurity",
    ),
    "registrar / DNS / cloud": (
        "cloudflare",
        "godaddy",
        "namecheap",
        "porkbun",
        "route53",
        "amazonaws",
        "azure",
        "digitalocean",
        "linode",
        "vultr",
        "hetzner",
    ),
    "government / health / tax": ("healthcare", "mychart", "medicare", "turbotax", "hrblock"),
}
# Short words matched only as whole tokens, to limit false positives.
_TOKEN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "email": ("mail", "email"),
    # "cas" is Apereo CAS, the school SSO (sso.example.edu), as a host label or id.
    "SSO / identity": ("sso", "identity", "cas"),
    "financial": ("chase", "crypto", "wallet", "broker", "brokerage"),
    "registrar / DNS / cloud": ("aws", "gcp", "dns", "registrar"),
    "government / health / tax": ("gov", "irs", "ssa", "tax", "health", "nhs"),
    "admin / recovery": ("admin", "root", "recovery", "superuser"),
}


def _searchable_text(credential_id: str, name: str, origins: Iterable[str]) -> str:
    hosts = [urlsplit(origin).hostname or "" for origin in origins]
    return " ".join([credential_id, name, *hosts]).lower()


def excluded_category(credential_id: str, name: str, origins: Iterable[str]) -> str | None:
    """Return the first excluded category this credential looks like, or None.

    Args:
        credential_id: The new credential's id.
        name: Its display name.
        origins: Its registered origins.

    Returns:
        A category label such as "financial", or None.
    """
    text = _searchable_text(credential_id, name, origins)
    tokens = set(re.split(r"[^a-z0-9]+", text))
    for category, keywords in _SUBSTRING_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    for category, keywords in _TOKEN_KEYWORDS.items():
        if tokens.intersection(keywords):
            return category
    return None
