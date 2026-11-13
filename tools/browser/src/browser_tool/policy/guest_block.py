"""Layer 1 of the container block: hosts a docker job's browser may never reach.

A page in a container under allow_all could otherwise reach this PC's own
services (through Docker's host alias or the PC's addresses) and the private
LAN. The docker backend builds its HostPolicy with a GuestBlock, which refuses,
whatever [policy] says:
- docker.internal, localhost and their subdomains;
- any IP-literal host that isn't globally routable (ipaddress.is_global, after
  unwrapping an IPv4-mapped IPv6 address), which also catches CGNAT 100.64/10
  that is_private misses;
- the host's own IPv4 addresses, read live on every check.
Layer 2, the guest's iptables, is the real boundary (DNS rebinding beats name
rules); it rejects BLOCKED_GUEST_CIDRS plus the host addresses. See
refdocs/research/docker-browser.md section 5.
"""

import ipaddress
import socket
from collections.abc import Callable, Collection

from browser_tool.policy.host_patterns import normalize_host, parse_host_pattern

# One list for both layers. The guest's iptables rejects every packet to these.
BLOCKED_GUEST_CIDRS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "127.0.0.0/8",
)
GUEST_DENIED_HOSTS = ("docker.internal", "*.docker.internal", "localhost", "*.localhost")
_DENIED_PATTERNS = tuple(parse_host_pattern(host) for host in GUEST_DENIED_HOSTS)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
# What the numeric IPv4 forms are made of; anything else is a name.
_LEGACY_IPV4_CHARS = frozenset("0123456789abcdefx.")


class GuestBlock:
    """The fixed name and address rules plus the host's live addresses."""

    def __init__(self, host_ips: Callable[[], Collection[str]]):
        """Args: host_ips: Returns the host's IPv4 addresses; called on every check."""
        self._host_ips = host_ips

    def is_blocked(self, host: str) -> bool:
        """True if a container's browser must not reach `host` (a URL's hostname).

        A name that can't be read isn't blocked here; HostPolicy refuses it anyway.
        """
        cleaned = host.strip().strip("[]").rstrip(".").lower()
        address = _ip_literal(cleaned)
        if address is not None:
            return not address.is_global or str(address) in self._host_ips()
        try:
            normalized = normalize_host(cleaned)
        except ValueError:
            return False
        return any(pattern.matches(normalized) for pattern in _DENIED_PATTERNS)

    def resolver_hosts(self) -> list[str]:
        """The names and host IPs to fail at DNS too (see resolver_rules)."""
        return [*GUEST_DENIED_HOSTS, *sorted(self._host_ips())]


def _ip_literal(host: str) -> IPAddress | None:
    """The address `host` spells, with an IPv4-mapped IPv6 address unwrapped, else None.

    Also reads the short, decimal, hex and octal IPv4 forms (127.1, 2130706433,
    0x7f000001, 0177.0.0.1) that Chromium canonicalizes to a dotted address.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return _legacy_ipv4(host)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _legacy_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """An IPv4 address in a non-dotted-quad form, read the way inet_aton does, else None."""
    if not host or not set(host) <= _LEGACY_IPV4_CHARS:
        return None
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None
