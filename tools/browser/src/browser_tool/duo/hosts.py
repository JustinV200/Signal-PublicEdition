"""Is this URL a Duo two-factor prompt? Host matching for duosecurity.com.

Duo serves its prompts (the Universal Prompt a login redirects to, and the
older embedded iframe) from duosecurity.com and its subdomains, such as
api-1a2b3c4d.duosecurity.com. Only the parsed hostname counts, so lookalikes
such as evil-duosecurity.com or duosecurity.com.evil.com, and a Duo host that
only appears in a path or query, don't match.

Default-deny: a network URL whose host can't be read counts as Duo, because the
lockout built on this check must fail closed.
"""

from browser_tool.policy import NETWORK_SCHEMES, host_of, scheme_of

DUO_DOMAIN = "duosecurity.com"
# blob:https://host/... and filesystem:https://host/... documents belong to the
# inner URL's origin, so the inner URL is what gets checked.
WRAPPING_SCHEMES = frozenset({"blob", "filesystem"})


def is_duo_host(host: str) -> bool:
    """True for duosecurity.com and any subdomain of it.

    Args:
        host: A bare host name; case and a trailing dot are ignored.
    """
    cleaned = host.strip().rstrip(".").lower()
    return cleaned == DUO_DOMAIN or cleaned.endswith("." + DUO_DOMAIN)


def is_duo_url(url: str) -> bool:
    """True when a document at `url` would be a Duo page, or when that can't be told.

    Args:
        url: A frame's URL as the browser reports it.

    Returns:
        True for a network URL on a Duo host or with an unreadable host; False for
        other hosts and for URLs with no host at all (about:, data:, "").
    """
    if scheme_of(url) in WRAPPING_SCHEMES:
        url = url.partition(":")[2]
    if scheme_of(url) not in NETWORK_SCHEMES:
        return False
    host = host_of(url)
    return host is None or is_duo_host(host)
