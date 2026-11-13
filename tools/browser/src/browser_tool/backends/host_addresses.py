"""This PC's IPv4 addresses, for the docker jobs' host block (both layers).

A container's browser must not reach the host through any of its addresses,
including a public one, which no private range covers. The list is
read again on every tool call; a job ends when a new address appears (a new
DHCP lease, another network), so the next job's firewall gets the new list.
Addresses are only ever added: blocking one the PC used to have is harmless.
"""

import logging
import socket
from collections.abc import Callable, Collection

from browser_tool.policy import BLOCKED_GUEST_CIDRS

logger = logging.getLogger(__name__)


def lookup_host_ipv4s() -> frozenset[str]:
    """The host's IPv4 addresses as the resolver lists them for its own name.

    Link-local addresses (Bluetooth's 169.254.x.x) can be missing; 169.254/16 is
    in BLOCKED_GUEST_CIDRS anyway.

    Raises:
        OSError: If the lookup fails.
    """
    infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    return frozenset(str(info[4][0]) for info in infos)


class HostAddresses:
    """Every IPv4 address this PC has had since the server started."""

    def __init__(self, lookup: Callable[[], Collection[str]] = lookup_host_ipv4s):
        """Args: lookup: Returns the current addresses; tests pass a fake."""
        self._lookup = lookup
        self._seen: frozenset[str] = frozenset()

    def seen(self) -> frozenset[str]:
        """The addresses known so far (what Layer 1 refuses)."""
        return self._seen

    def refresh(self) -> frozenset[str]:
        """Look the addresses up again and return all of them, old and new.

        A failed lookup keeps the last list, with a warning, rather than ending
        the job or opening the block.
        """
        try:
            self._seen = self._seen | frozenset(self._lookup())
        except OSError as error:
            logger.warning("couldn't list the host's addresses (%s)", type(error).__name__)
        return self._seen


def block_cidrs(host_ips: Collection[str]) -> str:
    """SIGNAL_BLOCK_CIDRS for a job: the fixed ranges plus each host address as a /32."""
    return ",".join([*BLOCKED_GUEST_CIDRS, *(f"{address}/32" for address in sorted(host_ips))])
