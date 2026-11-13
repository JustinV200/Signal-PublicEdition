"""The domain allow/deny decision for a URL.

Rules, in order:
1. Opaque-origin documents (about:blank, about:srcdoc, data:, blob:) are never
   "allowed": callers treat them as origin mismatches.
2. Non-network schemes (file:, edge:, chrome-error:, javascript: ...) are refused.
3. With a guest block (docker jobs only), a host it lists is refused, whatever
   the lists say (see guest_block).
4. A host matching the denylist is refused (deny always wins).
5. With allow-all switched on, every remaining host is allowed ("allow all, but log").
6. Otherwise the host must match an allowlist pattern; an empty allowlist blocks all.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from browser_tool.policy.guest_block import GuestBlock
from browser_tool.policy.host_patterns import HostPattern, normalize_host, parse_host_pattern
from browser_tool.policy.urls import NETWORK_SCHEMES, OPAQUE_SCHEMES, scheme_of

# PolicyDecision.reason values.
REASON_ALLOWLISTED = "allowlisted"
REASON_ALLOW_ALL = "allow_all"
REASON_DENYLISTED = "denylisted"
REASON_NOT_ALLOWLISTED = "not_allowlisted"
REASON_OPAQUE_ORIGIN = "opaque_origin"
REASON_UNSUPPORTED_SCHEME = "unsupported_scheme"
REASON_BAD_URL = "bad_url"
REASON_GUEST_BLOCKED = "guest_blocked"


@dataclass(frozen=True)
class PolicyDecision:
    """Result of checking one URL. `host` is the normalized host when there is one."""

    is_allowed: bool
    reason: str
    host: str | None = None


class HostPolicy:
    """Immutable allow/deny lists plus the matching logic."""

    def __init__(
        self,
        allow: Sequence[HostPattern] = (),
        deny: Sequence[HostPattern] = (),
        *,
        is_allow_all: bool = False,
        guest_block: GuestBlock | None = None,
    ):
        """Build a policy from parsed patterns (see parse_host_pattern).

        Args:
            allow: Allowed host patterns. Empty (and not allow-all) blocks everything.
            deny: Always-blocked host patterns.
            is_allow_all: Allow every host not denied, ignoring `allow`.
            guest_block: Hosts a container's browser may never reach (docker jobs).
        """
        self.allow_patterns: tuple[HostPattern, ...] = tuple(allow)
        self.deny_patterns: tuple[HostPattern, ...] = tuple(deny)
        self.is_allow_all = is_allow_all
        self.guest_block = guest_block

    @classmethod
    def from_strings(
        cls,
        allow: Sequence[str],
        deny: Sequence[str],
        *,
        is_allow_all: bool = False,
        guest_block: GuestBlock | None = None,
    ) -> "HostPolicy":
        """Parse pattern strings from config.

        Raises:
            ValueError: If any pattern is malformed.
        """
        return cls(
            [parse_host_pattern(p) for p in allow],
            [parse_host_pattern(p) for p in deny],
            is_allow_all=is_allow_all,
            guest_block=guest_block,
        )

    def check_host(self, host: str) -> PolicyDecision:
        """Decide for a bare host name (normalized here)."""
        # Before normalizing: the block reads IP literals, IPv6 ones included.
        if self.guest_block is not None and self.guest_block.is_blocked(host):
            return PolicyDecision(False, REASON_GUEST_BLOCKED)
        try:
            normalized = normalize_host(host)
        except ValueError:
            return PolicyDecision(False, REASON_BAD_URL)
        if any(pattern.matches(normalized) for pattern in self.deny_patterns):
            return PolicyDecision(False, REASON_DENYLISTED, normalized)
        if self.is_allow_all:
            return PolicyDecision(True, REASON_ALLOW_ALL, normalized)
        if any(pattern.matches(normalized) for pattern in self.allow_patterns):
            return PolicyDecision(True, REASON_ALLOWLISTED, normalized)
        return PolicyDecision(False, REASON_NOT_ALLOWLISTED, normalized)

    def check_url(self, url: str) -> PolicyDecision:
        """Decide for a full URL (page, frame or request URL)."""
        scheme = scheme_of(url)
        if scheme in OPAQUE_SCHEMES:
            return PolicyDecision(False, REASON_OPAQUE_ORIGIN)
        if scheme not in NETWORK_SCHEMES:
            return PolicyDecision(False, REASON_UNSUPPORTED_SCHEME)
        try:
            # .hostname drops userinfo, so "https://good.com@evil.com" checks evil.com.
            host = urlsplit(url).hostname
        except ValueError:
            return PolicyDecision(False, REASON_BAD_URL)
        if not host:
            return PolicyDecision(False, REASON_BAD_URL)
        return self.check_host(host)
