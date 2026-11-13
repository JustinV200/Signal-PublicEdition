"""Origin parsing and exact matching, which binds each credential to the sites it belongs to.

A credential fills only where the top-level page and every frame down to the
password field have an origin exactly equal to one of its registered origins:
https only, same ASCII (punycode) host, same port. There are no wildcards and
no subdomain matching. about:blank, about:srcdoc, data: and blob: frames have
no https origin of their own, so they never match.
"""

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

HTTPS_SCHEME = "https"
DEFAULT_HTTPS_PORT = 443

# One DNS label: letters, digits and inner hyphens, 1-63 chars.
_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_HOSTNAME_PATTERN = re.compile(rf"^{_LABEL}(\.{_LABEL})*$")

# Shown instead of an origin when a URL can't be described safely.
UNPARSABLE_LABEL = "<unparsable>"


class OriginError(ValueError):
    """A URL is not an acceptable https origin."""


def _canonical_host(raw_host: str) -> str:
    """Lowercase an ASCII hostname, rejecting anything that isn't a plain DNS name.

    Non-ASCII hosts are refused rather than converted: Python's `idna` codec is
    IDNA2003 (it maps "faß.de" to "fass.de", a different site from the
    browser's IDNA2008 "xn--fa-hia.de"). Browsers report frame URLs in punycode
    already, so only owner input can hit this.
    """
    if ":" in raw_host:
        raise OriginError("IPv6 literal origins are not supported")
    if not raw_host.isascii():
        raise OriginError(
            "internationalised hostnames must be entered in punycode form (xn--...), "
            "exactly as the browser's address bar shows them when copied"
        )
    host = raw_host.lower()
    if not _HOSTNAME_PATTERN.match(host):
        raise OriginError("hostname has invalid characters")
    return host


def origin_of_url(url: str) -> str:
    """Return the canonical https origin of `url`, e.g. "https://github.com" or "https://x.test:8443".

    The path, query and fragment are ignored. The default port 443 is omitted.

    Args:
        url: Any URL string.

    Returns:
        The origin string.

    Raises:
        OriginError: Not https, has user info, or has an invalid host or port.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise OriginError("not a valid URL") from None
    if parts.scheme.lower() != HTTPS_SCHEME:
        raise OriginError("only https origins are allowed")
    # A decoy host in user info ("https://github.com@evil.test") is a known bypass.
    if "@" in parts.netloc:
        raise OriginError("URLs with user info are not allowed")
    if not parts.hostname:
        raise OriginError("URL has no host")
    host = _canonical_host(parts.hostname)
    if port is None or port == DEFAULT_HTTPS_PORT:
        return f"{HTTPS_SCHEME}://{host}"
    return f"{HTTPS_SCHEME}://{host}:{port}"


def parse_registered_origin(text: str) -> str:
    """Validate an origin the owner is registering for a credential.

    Stricter than `origin_of_url`: a path, query or fragment is refused, so the
    owner never believes a credential is scoped to a path.

    Args:
        text: What the owner typed, e.g. "https://github.com".

    Returns:
        The canonical origin string.

    Raises:
        OriginError: Not a bare https origin.
    """
    stripped = text.strip()
    try:
        parts = urlsplit(stripped)
    except ValueError:
        raise OriginError("not a valid URL") from None
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise OriginError("give a bare origin such as https://example.com (no path or query)")
    return origin_of_url(stripped)


def url_matches_origins(url: str, allowed_origins: Iterable[str]) -> bool:
    """Return True if `url` has an https origin exactly equal to one of `allowed_origins`.

    Opaque or inherited-origin URLs (about:, data:, blob:, javascript:) always
    return False.
    """
    try:
        origin = origin_of_url(url)
    except OriginError:
        return False
    return origin in set(allowed_origins)


def describe_origin(url: str) -> str:
    """Return a short, token-free label for `url`, for dialogs and the audit log.

    http(s) URLs become "scheme://host[:port]". Everything else becomes just its
    scheme ("data:", "blob:") or the bare about: URL, because the rest of such
    URLs can carry page content or tokens.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return UNPARSABLE_LABEL
    scheme = parts.scheme.lower()
    if scheme in ("http", "https") and parts.hostname:
        suffix = f":{port}" if port is not None else ""
        return f"{scheme}://{parts.hostname}{suffix}"
    if scheme == "about":
        return f"about:{parts.path}"
    return f"{scheme}:" if scheme else UNPARSABLE_LABEL
