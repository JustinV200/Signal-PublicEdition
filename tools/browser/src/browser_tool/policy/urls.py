"""Small URL helpers shared by the policy, the request guard and the actions.

Logs and confirmation dialogs show origins (scheme://host:port), never full URLs,
because query strings and fragments often carry tokens.
"""

from urllib.parse import urlsplit

# Schemes that reach the network and are subject to the allow/deny lists.
NETWORK_SCHEMES = frozenset({"http", "https", "ws", "wss"})
# Schemes whose documents have an opaque or inherited origin (about:blank,
# about:srcdoc, data:, blob:). They are treated as origin mismatches.
OPAQUE_SCHEMES = frozenset({"about", "data", "blob"})


def scheme_of(url: str) -> str:
    """Return the lowercased scheme of `url`, or "" if it has none."""
    head, separator, _ = url.partition(":")
    return head.strip().lower() if separator else ""


def origin_of(url: str) -> str:
    """Return a display origin for `url`, safe to log.

    Args:
        url: Any URL string.

    Returns:
        "scheme://host[:port]" for network URLs, "about:srcdoc"-style "scheme:path"
        for opaque URLs (without any query), or "<scheme>:" for everything else.
    """
    scheme = scheme_of(url)
    if scheme in NETWORK_SCHEMES:
        try:
            parts = urlsplit(url)
            port = f":{parts.port}" if parts.port else ""
        except ValueError:
            return f"{scheme}://<invalid>"
        host = parts.hostname or ""
        # .hostname drops an IPv6 literal's brackets; put them back, or http://[::1]:8080
        # and http://[::1:8080] would both read http://::1:8080 and compare equal.
        if ":" in host:
            host = f"[{host}]"
        return f"{scheme}://{host}{port}"
    if scheme == "about":
        # about:blank / about:srcdoc carry no secrets; drop any query or fragment.
        return url.split("?", 1)[0].split("#", 1)[0]
    return f"{scheme}:"


def display_url(url: str) -> str:
    """Return `url` as origin + path, for showing to the model.

    Query strings and fragments are dropped because they often carry session
    tokens or OAuth codes; userinfo is dropped by origin_of.
    """
    if scheme_of(url) not in NETWORK_SCHEMES:
        return origin_of(url)
    try:
        path = urlsplit(url).path
    except ValueError:
        path = ""
    return origin_of(url) + path


def host_of(url: str) -> str | None:
    """The hostname of a network URL, without port or trailing dot.

    Args:
        url: Any URL string.

    Returns:
        E.g. "portal.example.edu", or None for a non-network URL or one whose host
        can't be parsed.
    """
    if scheme_of(url) not in NETWORK_SCHEMES:
        return None
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.rstrip(".") or None
