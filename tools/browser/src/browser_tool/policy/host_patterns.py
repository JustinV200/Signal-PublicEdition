"""Host patterns for the domain allow/deny lists.

Two forms only, mirroring Chromium's host-resolver-rules wildcards:
- "example.com"    matches exactly example.com
- "*.example.com"  matches any subdomain of example.com (not example.com itself)

Hosts are compared after IDNA (punycode) normalization and lowercasing, so a
Unicode lookalike can't match an ASCII entry by accident.
"""

import re
from dataclasses import dataclass

SUBDOMAIN_PREFIX = "*."
# Letters, digits, hyphens and underscores in dot-separated labels (IPv4 fits too).
_HOST_RE = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?(\.[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?)*$")


def normalize_host(host: str) -> str:
    """Lowercase a host, drop a trailing dot and convert it to its IDNA ASCII form.

    Args:
        host: A bare host name such as "Example.COM." or "bücher.de".

    Returns:
        The normalized host, e.g. "example.com" or "xn--bcher-kva.de".

    Raises:
        ValueError: If the host is empty or not a valid host name.
    """
    cleaned = host.strip().rstrip(".").lower()
    try:
        ascii_host = cleaned.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError(f"invalid host name: {host!r}") from error
    if not _HOST_RE.match(ascii_host):
        raise ValueError(f"invalid host name: {host!r}")
    return ascii_host


@dataclass(frozen=True)
class HostPattern:
    """One allow/deny entry: a normalized host plus whether it means "subdomains of"."""

    host: str
    is_subdomain_wildcard: bool

    def matches(self, host: str) -> bool:
        """Return True if `host` (already normalized) matches this pattern."""
        if self.is_subdomain_wildcard:
            return host.endswith("." + self.host)
        return host == self.host

    def __str__(self) -> str:
        return SUBDOMAIN_PREFIX + self.host if self.is_subdomain_wildcard else self.host


def parse_host_pattern(text: str) -> HostPattern:
    """Parse "example.com" or "*.example.com" into a HostPattern.

    Args:
        text: The pattern as written in browser.toml.

    Returns:
        The parsed pattern.

    Raises:
        ValueError: If the pattern has a scheme, port, path, other wildcards, or an
            invalid host name.
    """
    is_wildcard = text.startswith(SUBDOMAIN_PREFIX)
    host_text = text[len(SUBDOMAIN_PREFIX) :] if is_wildcard else text
    if any(char in host_text for char in "*:/@[]"):
        raise ValueError(
            f"bad host pattern {text!r}: use 'example.com' or '*.example.com' "
            "(no scheme, port, path or other wildcards)"
        )
    return HostPattern(host=normalize_host(host_text), is_subdomain_wildcard=is_wildcard)
