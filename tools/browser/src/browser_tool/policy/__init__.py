"""Public API of browser_tool.policy: domain allow/deny decisions and URL helpers.

Pure Python, no Playwright: the session package applies these decisions to the browser.
"""

from browser_tool.policy.guest_block import BLOCKED_GUEST_CIDRS, GuestBlock
from browser_tool.policy.host_patterns import HostPattern, normalize_host, parse_host_pattern
from browser_tool.policy.host_policy import (
    REASON_ALLOW_ALL,
    REASON_ALLOWLISTED,
    REASON_BAD_URL,
    REASON_DENYLISTED,
    REASON_GUEST_BLOCKED,
    REASON_NOT_ALLOWLISTED,
    REASON_OPAQUE_ORIGIN,
    REASON_UNSUPPORTED_SCHEME,
    HostPolicy,
    PolicyDecision,
)
from browser_tool.policy.resolver_rules import build_host_resolver_rules, build_resolver_args
from browser_tool.policy.urls import (
    NETWORK_SCHEMES,
    OPAQUE_SCHEMES,
    display_url,
    host_of,
    origin_of,
    scheme_of,
)

__all__ = [
    "BLOCKED_GUEST_CIDRS",
    "NETWORK_SCHEMES",
    "OPAQUE_SCHEMES",
    "REASON_ALLOWLISTED",
    "REASON_ALLOW_ALL",
    "REASON_BAD_URL",
    "REASON_DENYLISTED",
    "REASON_GUEST_BLOCKED",
    "REASON_NOT_ALLOWLISTED",
    "REASON_OPAQUE_ORIGIN",
    "REASON_UNSUPPORTED_SCHEME",
    "GuestBlock",
    "HostPattern",
    "HostPolicy",
    "PolicyDecision",
    "build_host_resolver_rules",
    "build_resolver_args",
    "display_url",
    "host_of",
    "normalize_host",
    "origin_of",
    "parse_host_pattern",
    "scheme_of",
]
