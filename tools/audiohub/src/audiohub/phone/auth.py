"""Who may use the phone page: the session cookie and the Host and Origin checks.

The page server binds 127.0.0.1, and Tailscale Serve forwards the phone to it,
so any local web page could reach it too. Three checks stop that:
- the session cookie, an HMAC of the server's secret token, which only the
  token link from `audiohub phone-link` sets (compared in constant time);
- the Host header, which must name localhost or a configured Tailscale host,
  so a DNS-rebinding page can't pose as the server;
- the Origin of the WebSocket handshake, which must be one of those hosts and
  the page's own origin, port included. Cookies and SameSite ignore ports, so
  without the port check a script on another loopback port (a dev server, a
  notebook) could open the socket with the owner's cookie.
"""

import hashlib
import hmac
from collections.abc import Iterable
from urllib.parse import urlsplit

from audiohub.kernel import tokens_match

COOKIE_NAME = "audiohub_phone"
# Fixed HMAC message: the cookie proves knowledge of the token without being it.
_COOKIE_CONTEXT = b"audiohub phone session v1"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


def session_cookie_value(token: str) -> str:
    """The session cookie value for `token`: a hex HMAC-SHA256, so the cookie never holds it."""
    return hmac.new(token.encode(), _COOKIE_CONTEXT, hashlib.sha256).hexdigest()


def is_session_cookie_valid(cookie: str | None, token: str) -> bool:
    """Whether a request's cookie value matches `token`'s, in constant time."""
    return cookie is not None and tokens_match(cookie, session_cookie_value(token))


def allowed_hostnames(configured: Iterable[str]) -> frozenset[str]:
    """Localhost plus the configured hosts, normalised for comparison."""
    return LOCAL_HOSTS | {_normalise(host) for host in configured}


def is_host_allowed(host_header: str | None, allowed: frozenset[str]) -> bool:
    """Whether a Host header (name and optional port) names an allowed host."""
    if not host_header:
        return False
    # "[::1]:8781" style IPv6 hosts are never allowed; the server binds IPv4.
    name = host_header.rsplit(":", 1)[0] if ":" in host_header else host_header
    return _normalise(name) in allowed


def is_origin_allowed(origin: str | None, allowed: frozenset[str]) -> bool:
    """Whether an Origin header is an allowed host: https, or http for localhost only."""
    if not origin:
        return False
    try:
        parts = urlsplit(origin)
        hostname = parts.hostname
    except ValueError:
        return False
    if hostname is None or _normalise(hostname) not in allowed:
        return False
    if parts.scheme == "https":
        return True
    return parts.scheme == "http" and _normalise(hostname) in LOCAL_HOSTS


def is_same_origin(origin: str | None, host_header: str | None) -> bool:
    """Whether Origin is the server the request was sent to: same host and port as Host.

    A missing port means the scheme's default, so `https://pc.ts.net` matches
    a Host of `pc.ts.net` or `pc.ts.net:443`.
    """
    if not origin or not host_header:
        return False
    try:
        origin_parts = urlsplit(origin)
        host_parts = urlsplit(f"//{host_header}")
        default_port = _DEFAULT_PORTS.get(origin_parts.scheme)
        origin_port = origin_parts.port or default_port
        host_port = host_parts.port or default_port
    except ValueError:
        return False
    if origin_parts.hostname is None or host_parts.hostname is None:
        return False
    is_same_host = _normalise(origin_parts.hostname) == _normalise(host_parts.hostname)
    return is_same_host and origin_port == host_port


def _normalise(host: str) -> str:
    # Host names are case-insensitive, and "name." is the same fully qualified name.
    return host.strip().lower().rstrip(".")
